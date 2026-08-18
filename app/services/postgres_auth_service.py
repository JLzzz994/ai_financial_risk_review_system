"""PostgreSQL 用户认证服务。"""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any, Protocol
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError
from app.repositories.sql_user_repository import SqlUserRepository, StoredUser
from app.schemas.auth import AuthToken, LoginCommand, Principal
from app.services.auth_service import (
    RateLimiter,
    RedisRateLimiter,
    RedisRevocationStore,
    RevocationStore,
)

_password_hasher = PasswordHasher()


class AuthUserRepository(Protocol):
    """认证服务依赖的异步用户查询契约。"""

    async def find_by_username(self, session: AsyncSession, username: str) -> StoredUser | None:
        """按用户名查询认证记录。"""

    async def find_by_id(self, session: AsyncSession, user_id: UUID) -> StoredUser | None:
        """按用户 ID 查询最新主体。"""


class PostgresAuthService:
    """以 PostgreSQL 为用户事实源、以 Redis 保存撤销与限流状态。"""

    def __init__(
        self,
        repository: AuthUserRepository | None = None,
        *,
        revocation_store: RevocationStore | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """初始化认证依赖；单元测试可注入内存实现。"""
        self.repository = repository or SqlUserRepository()
        self.revocation_store = revocation_store or RedisRevocationStore()
        self.rate_limiter = rate_limiter or RedisRateLimiter()

    async def authenticate(
        self,
        session: AsyncSession,
        command: LoginCommand,
        client_ip: str | None = None,
    ) -> AuthToken:
        """查询数据库用户、校验 Argon2 密码并签发短期 JWT。"""
        username = command.username
        limiter_keys = [f"user:{username}"]
        if client_ip:
            limiter_keys.append(f"ip:{client_ip}")
        self._ensure_not_limited(limiter_keys)
        try:
            record = await self.repository.find_by_username(session, username)
        except Exception as exc:
            raise AppError("auth_dependency_unavailable", "认证依赖暂不可用", 503) from exc
        if record is None or record.principal.disabled or record.principal.status != "active":
            self._record_login_failure(limiter_keys)
            raise AppError("invalid_credentials", "用户名或密码错误", 401)
        try:
            _password_hasher.verify(record.password_hash, command.password)
        except Exception as exc:
            self._record_login_failure(limiter_keys)
            raise AppError("invalid_credentials", "用户名或密码错误", 401) from exc
        self._clear_limiters(limiter_keys)
        token = self._issue_token(record.principal)
        self._record_audit("login_success", username, record.user_id, client_ip)
        return token

    async def get_current_principal(self, session: AsyncSession, token: str) -> Principal:
        """验签、检查撤销并从数据库读取最新用户状态与权限版本。"""
        payload = self._claims(token)
        try:
            revoked = self.revocation_store.is_revoked(str(payload["jti"]))
        except Exception as exc:
            raise AppError("auth_dependency_unavailable", "认证依赖暂不可用", 503) from exc
        if revoked:
            raise AppError("token_revoked", "认证令牌已退出登录", 401)
        try:
            user_id = UUID(str(payload["sub"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError("invalid_token", "认证令牌无效", 401) from exc
        try:
            record = await self.repository.find_by_id(session, user_id)
        except Exception as exc:
            raise AppError("auth_dependency_unavailable", "认证依赖暂不可用", 503) from exc
        if record is None:
            raise AppError("invalid_token", "认证令牌无效", 401)
        if record.principal.disabled or record.principal.status != "active":
            raise AppError("account_disabled", "账号已禁用", 401)
        if int(payload.get("permission_version", 0)) != record.principal.permission_version:
            raise AppError("token_stale", "权限已变更，请重新登录", 401)
        return record.principal

    async def logout(self, token: str) -> None:
        """按 JWT 剩余有效期撤销令牌，重复退出保持幂等。"""
        payload = self._claims(token)
        try:
            expires_at = datetime.fromtimestamp(float(payload["exp"]), UTC)
            ttl_seconds = max(int((expires_at - datetime.now(UTC)).total_seconds()), 1)
            self.revocation_store.revoke(str(payload["jti"]), ttl_seconds)
        except AppError:
            raise
        except Exception as exc:
            raise AppError("auth_dependency_unavailable", "认证依赖暂不可用", 503) from exc
        actor_id = UUID(str(payload["sub"])) if payload.get("sub") else None
        self._record_audit("logout", str(payload.get("username", "")), actor_id, None)

    def _ensure_not_limited(self, keys: list[str]) -> None:
        """检查 Redis 限流状态，依赖异常时认证失败关闭。"""
        try:
            blocked = any(
                self.rate_limiter.is_blocked(
                    key,
                    settings.auth_rate_limit_max_attempts,
                    settings.auth_rate_limit_window_seconds,
                )
                for key in keys
            )
        except Exception as exc:
            raise AppError("auth_dependency_unavailable", "认证依赖暂不可用", 503) from exc
        if blocked:
            raise AppError("login_rate_limited", "登录尝试过于频繁，请稍后重试", 429)

    def _record_login_failure(self, keys: list[str]) -> None:
        """记录失败次数；不记录密码或用户敏感资料。"""
        try:
            for key in keys:
                self.rate_limiter.record_failure(key, settings.auth_rate_limit_window_seconds)
        except Exception as exc:
            raise AppError("auth_dependency_unavailable", "认证依赖暂不可用", 503) from exc

    def _clear_limiters(self, keys: list[str]) -> None:
        """登录成功后清理所有关联限流键。"""
        try:
            for key in keys:
                self.rate_limiter.clear(key)
        except Exception as exc:
            raise AppError("auth_dependency_unavailable", "认证依赖暂不可用", 503) from exc

    @staticmethod
    def _issue_token(principal: Principal) -> AuthToken:
        """构造包含权限版本和组织范围的 JWT。"""
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=settings.jwt_expire_minutes)
        payload = {
            "sub": str(principal.user_id),
            "username": principal.username,
            "roles": [role.value for role in principal.roles],
            "org_scope": sorted(principal.org_scope),
            "permission_version": principal.permission_version,
            "jti": token_urlsafe(24),
            "iss": settings.jwt_issuer,
            "iat": now,
            "exp": expires_at,
        }
        access_token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        return AuthToken(
            access_token=access_token,
            expires_in=max(int((expires_at - now).total_seconds()), 1),
            expires_at=expires_at,
            user=principal,
        )

    @staticmethod
    def _claims(token: str) -> Mapping[str, Any]:
        """验签并转换统一认证错误。"""
        try:
            return jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
                issuer=settings.jwt_issuer,
                options={"require": ["sub", "jti", "exp", "iat", "iss"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AppError("token_expired", "认证令牌已过期", 401) from exc
        except Exception as exc:
            raise AppError("invalid_token", "认证令牌无效", 401) from exc

    @staticmethod
    def _record_audit(
        action: str, username: str, actor_id: UUID | None, client_ip: str | None
    ) -> None:
        """输出脱敏认证审计摘要，后续由审计仓储接管持久化。"""
        import logging

        logging.getLogger("financial_review.auth").info(
            "auth_audit action=%s username_hash=%s actor_id=%s client_ip=%s",
            action,
            sha256(username.encode("utf-8")).hexdigest() if username else None,
            actor_id,
            client_ip,
        )


postgres_auth_service = PostgresAuthService()


__all__ = ["PostgresAuthService", "postgres_auth_service"]
