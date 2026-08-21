"""认证、令牌撤销和登录限流服务。

业务代码只依赖本文件定义的存储协议。生产环境可以注入 Redis 实现，单元测试
使用内存实现；两种实现都遵循 Redis 不可用时认证失败关闭（fail closed）。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any, Protocol
from uuid import UUID

import jwt
from argon2 import PasswordHasher

from app.config import settings
from app.errors import AppError
from app.schemas.auth import AuthToken, LoginCommand, Principal, RoleCode

_password_hasher = PasswordHasher()


class RevocationStore(Protocol):
    """Token 撤销存储协议；实现必须按令牌剩余时间自动过期。"""

    def revoke(self, jti: str, ttl_seconds: int) -> None:
        """写入撤销标记。"""

    def is_revoked(self, jti: str) -> bool:
        """检查令牌是否已经撤销。"""


class RateLimiter(Protocol):
    """登录失败限流协议。"""

    def is_blocked(self, key: str, max_attempts: int, window_seconds: int) -> bool:
        """判断账号或客户端是否已达到限流阈值。"""

    def record_failure(self, key: str, window_seconds: int) -> None:
        """记录一次失败登录。"""

    def clear(self, key: str) -> None:
        """登录成功后清理失败计数。"""


class InMemoryRevocationStore:
    """开发和测试使用的带 TTL 撤销存储。"""

    def __init__(self) -> None:
        """初始化空撤销集合。"""
        self._revoked: dict[str, datetime] = {}

    def revoke(self, jti: str, ttl_seconds: int) -> None:
        """保存撤销时间；过期时间不小于 1 秒，避免立即失效。"""
        self._revoked[jti] = datetime.now(UTC) + timedelta(seconds=max(ttl_seconds, 1))

    def is_revoked(self, jti: str) -> bool:
        """读取撤销状态并清理已经过期的标记。"""
        expires_at = self._revoked.get(jti)
        if expires_at is None:
            return False
        if expires_at <= datetime.now(UTC):
            self._revoked.pop(jti, None)
            return False
        return True


class RedisRevocationStore:
    """生产 Redis 撤销存储的轻量适配器。"""

    def __init__(self, client: object | None = None, key_prefix: str | None = None) -> None:
        """延迟创建 Redis 客户端，便于测试注入假客户端。"""
        self._client = client
        self._key_prefix = key_prefix or settings.auth_revocation_key_prefix

    @property
    def client(self) -> object:
        """获取 Redis 客户端；连接失败交给上层统一转换为 503。"""
        if self._client is None:
            try:
                from redis import Redis

                self._client = Redis.from_url(settings.redis_url, decode_responses=True)
            except Exception as exc:
                raise RuntimeError("Redis 撤销依赖不可用") from exc
        return self._client

    def _key(self, jti: str) -> str:
        """拼接带命名空间的撤销键。"""
        return f"{self._key_prefix}:{jti}"

    def revoke(self, jti: str, ttl_seconds: int) -> None:
        """写入 Redis 撤销键并设置剩余 TTL。"""
        client = self.client
        try:
            client.set(self._key(jti), "1", ex=max(ttl_seconds, 1))  # type: ignore[attr-defined]
        except Exception as exc:
            raise RuntimeError("Redis 撤销依赖不可用") from exc

    def is_revoked(self, jti: str) -> bool:
        """查询 Redis 撤销键是否存在。"""
        client = self.client
        try:
            return bool(client.exists(self._key(jti)))  # type: ignore[attr-defined]
        except Exception as exc:
            raise RuntimeError("Redis 撤销依赖不可用") from exc


class InMemoryRateLimiter:
    """带时间窗口的内存登录失败限流器。"""

    def __init__(self) -> None:
        """初始化账号/IP 失败记录。"""
        self._failures: dict[str, list[datetime]] = {}

    def _active_failures(self, key: str, window_seconds: int) -> list[datetime]:
        """返回窗口内失败记录并删除窗口外记录。"""
        threshold = datetime.now(UTC) - timedelta(seconds=window_seconds)
        active = [item for item in self._failures.get(key, []) if item > threshold]
        self._failures[key] = active
        return active

    def is_blocked(self, key: str, max_attempts: int, window_seconds: int) -> bool:
        """窗口内失败次数达到阈值时阻止继续登录。"""
        return len(self._active_failures(key, window_seconds)) >= max_attempts

    def record_failure(self, key: str, window_seconds: int) -> None:
        """追加当前失败时间。"""
        active = self._active_failures(key, window_seconds)
        active.append(datetime.now(UTC))
        self._failures[key] = active

    def clear(self, key: str) -> None:
        """登录成功后删除失败记录。"""
        self._failures.pop(key, None)


class RedisRateLimiter:
    """生产 Redis 登录失败限流器，按账号/IP 使用带 TTL 的计数键。"""

    def __init__(self, client: object | None = None, key_prefix: str | None = None) -> None:
        """延迟创建 Redis 客户端，便于测试注入假客户端。"""
        self._client = client
        self._key_prefix = key_prefix or "financial-review:auth:login-failures"

    @property
    def client(self) -> object:
        """获取 Redis 客户端；连接异常交给认证服务转换为 503。"""
        if self._client is None:
            try:
                from redis import Redis

                self._client = Redis.from_url(settings.redis_url, decode_responses=True)
            except Exception as exc:
                raise RuntimeError("Redis 限流依赖不可用") from exc
        return self._client

    def _key(self, key: str) -> str:
        """拼接限流命名空间，避免和业务缓存键冲突。"""
        return f"{self._key_prefix}:{key}"

    def is_blocked(self, key: str, max_attempts: int, window_seconds: int) -> bool:
        """读取窗口内失败次数，达到阈值即拒绝继续登录。"""
        try:
            count = self.client.get(self._key(key))  # type: ignore[attr-defined]
            return int(count or 0) >= max_attempts
        except Exception as exc:
            raise RuntimeError("Redis 限流依赖不可用") from exc

    def record_failure(self, key: str, window_seconds: int) -> None:
        """递增失败次数并为首次计数设置窗口 TTL。"""
        try:
            redis_key = self._key(key)
            count = int(self.client.incr(redis_key))  # type: ignore[attr-defined]
            if count == 1:
                self.client.expire(redis_key, max(window_seconds, 1))  # type: ignore[attr-defined]
        except Exception as exc:
            raise RuntimeError("Redis 限流依赖不可用") from exc

    def clear(self, key: str) -> None:
        """登录成功后清理账号和 IP 的失败计数。"""
        try:
            self.client.delete(self._key(key))  # type: ignore[attr-defined]
        except Exception as exc:
            raise RuntimeError("Redis 限流依赖不可用") from exc


@dataclass(frozen=True)
class AuthAuditEvent:
    """认证审计摘要，不保存密码、完整令牌或附件原文。"""

    action: str
    username_hash: str | None
    actor_id: UUID | None
    occurred_at: datetime
    client_ip: str | None = None
    request_id: str | None = None


class InMemoryAuthService:
    """开发和测试认证服务，生产环境通过仓储替换用户查询。"""

    def __init__(
        self,
        revocation_store: RevocationStore | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """初始化用户凭据、撤销存储、限流器和脱敏审计集合。"""
        self._users: dict[str, tuple[Principal, str]] = {}
        self._users_by_id: dict[UUID, str] = {}
        self.revocation_store = revocation_store or InMemoryRevocationStore()
        self.rate_limiter = rate_limiter or InMemoryRateLimiter()
        self.audit_events: list[AuthAuditEvent] = []

    def register(
        self,
        username: str,
        password: str,
        role: RoleCode = RoleCode.APPLICANT,
        organization_ids: set[str] | frozenset[str] | None = None,
    ) -> Principal:
        """注册测试用户并使用 Argon2id 保存密码哈希。"""
        if username in self._users:
            raise AppError("user_exists", "用户名已存在", 409)
        principal = Principal(
            user_id=UUID(int=len(self._users) + 1),
            username=username,
            roles=frozenset({role}),
            org_scope=frozenset(organization_ids or set()),
        )
        self._users[username] = (principal, _password_hasher.hash(password))
        self._users_by_id[principal.user_id] = username
        return principal

    def authenticate(
        self,
        command: LoginCommand | str,
        password: str | None = None,
        client_ip: str | None = None,
    ) -> AuthToken:
        """校验密码并签发包含 jti、权限版本和过期时间的短期 JWT。"""
        if isinstance(command, LoginCommand):
            username, raw_password = command.username, command.password
        else:
            username, raw_password = command, password or ""
        limiter_keys = [f"user:{username}"]
        if client_ip:
            limiter_keys.append(f"ip:{client_ip}")
        self._ensure_not_limited(limiter_keys)
        record = self._users.get(username)
        if record is None:
            self._record_login_failure(limiter_keys, username, None, client_ip)
            raise AppError("invalid_credentials", "用户名或密码错误", 401)
        principal, password_hash = record
        if principal.disabled or principal.status != "active":
            self._record_login_failure(limiter_keys, username, principal.user_id, client_ip)
            raise AppError("invalid_credentials", "用户名或密码错误", 401)
        try:
            _password_hasher.verify(password_hash, raw_password)
        except Exception as exc:
            self._record_login_failure(limiter_keys, username, principal.user_id, client_ip)
            raise AppError("invalid_credentials", "用户名或密码错误", 401) from exc
        for key in limiter_keys:
            self._safe_limiter_call(lambda key=key: self.rate_limiter.clear(key))
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=settings.jwt_expire_minutes)
        jti = token_urlsafe(24)
        payload = {
            "sub": str(principal.user_id),
            "username": principal.username,
            "roles": [role.value for role in principal.roles],
            "org_scope": sorted(principal.org_scope),
            "permission_version": principal.permission_version,
            "jti": jti,
            "iss": settings.jwt_issuer,
            "iat": now,
            "exp": expires_at,
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        self._record_audit("login_success", username, principal.user_id, client_ip)
        return AuthToken(
            access_token=token,
            expires_in=max(int((expires_at - now).total_seconds()), 1),
            expires_at=expires_at,
            user=principal,
        )

    def _ensure_not_limited(self, keys: list[str]) -> None:
        """检查账号/IP 限流；限流依赖异常时认证失败关闭。"""
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

    def _record_login_failure(
        self,
        keys: list[str],
        username: str,
        actor_id: UUID | None,
        client_ip: str | None,
    ) -> None:
        """记录限流失败和脱敏审计；依赖不可用时阻断认证。"""
        try:
            for key in keys:
                self.rate_limiter.record_failure(key, settings.auth_rate_limit_window_seconds)
        except Exception as exc:
            raise AppError("auth_dependency_unavailable", "认证依赖暂不可用", 503) from exc
        self._record_audit("login_failure", username, actor_id, client_ip)

    def _safe_limiter_call(self, operation: object) -> None:
        """执行清理；清理失败不能让已验证登录绕过认证。"""
        try:
            operation()  # type: ignore[operator]
        except Exception as exc:
            raise AppError("auth_dependency_unavailable", "认证依赖暂不可用", 503) from exc

    def _claims(self, token: str) -> Mapping[str, Any]:
        """验签并返回 JWT Claims，统一映射为 401。"""
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
                issuer=settings.jwt_issuer,
                options={"require": ["sub", "jti", "exp", "iat", "iss"]},
            )
            return payload
        except jwt.ExpiredSignatureError as exc:
            raise AppError("token_expired", "认证令牌已过期", 401) from exc
        except Exception as exc:
            raise AppError("invalid_token", "认证令牌无效", 401) from exc

    def decode(self, token: str) -> Principal:
        """兼容同步调用：仅验签并解析令牌，不跳过状态和撤销检查。"""
        payload = self._claims(token)
        return self._principal_from_claims(payload)

    async def get_current_principal(self, token: str) -> Principal:
        """验签、检查撤销、用户状态和权限版本后返回当前主体。"""
        payload = self._claims(token)
        jti = str(payload["jti"])
        try:
            revoked = self.revocation_store.is_revoked(jti)
        except Exception as exc:
            raise AppError("auth_dependency_unavailable", "认证依赖暂不可用", 503) from exc
        if revoked:
            raise AppError("token_revoked", "认证令牌已退出登录", 401)
        try:
            user_id = UUID(str(payload["sub"]))
        except (ValueError, TypeError, KeyError) as exc:
            raise AppError("invalid_token", "认证令牌无效", 401) from exc
        username = self._users_by_id.get(user_id)
        if username is None or username not in self._users:
            raise AppError("invalid_token", "认证令牌无效", 401)
        principal, _ = self._users[username]
        if principal.disabled or principal.status != "active":
            raise AppError("account_disabled", "账号已禁用", 401)
        if int(payload.get("permission_version", 0)) != principal.permission_version:
            raise AppError("token_stale", "权限已变更，请重新登录", 401)
        return principal

    async def logout(self, token: str) -> None:
        """将当前令牌 jti 写入撤销存储，重复退出保持幂等。"""
        payload = self._claims(token)
        expires_at = datetime.fromtimestamp(float(payload["exp"]), UTC)
        ttl_seconds = max(int((expires_at - datetime.now(UTC)).total_seconds()), 1)
        try:
            self.revocation_store.revoke(str(payload["jti"]), ttl_seconds)
        except Exception as exc:
            raise AppError("auth_dependency_unavailable", "认证依赖暂不可用", 503) from exc
        actor_id = UUID(str(payload["sub"])) if payload.get("sub") else None
        self._record_audit("logout", str(payload.get("username", "")), actor_id, None)

    def disable(self, user_id: UUID) -> None:
        """禁用用户，使其已签发令牌在下一次请求立即失效。"""
        principal, password_hash = self._record_by_id(user_id)
        updated = principal.model_copy(update={"disabled": True, "status": "disabled"})
        self._users[principal.username] = (updated, password_hash)

    def update_roles(
        self,
        user_id: UUID,
        roles: set[RoleCode] | frozenset[RoleCode],
        organization_ids: set[str] | frozenset[str] | None = None,
    ) -> Principal:
        """更新角色和组织范围并递增权限版本，使旧令牌失效。"""
        principal, password_hash = self._record_by_id(user_id)
        updated = principal.model_copy(
            update={
                "roles": frozenset(roles),
                "org_scope": frozenset(
                    organization_ids if organization_ids is not None else principal.org_scope
                ),
                "permission_version": principal.permission_version + 1,
            }
        )
        self._users[principal.username] = (updated, password_hash)
        return updated

    def _record_by_id(self, user_id: UUID) -> tuple[Principal, str]:
        """按用户 ID 获取内存用户记录。"""
        username = self._users_by_id.get(user_id)
        if username is None or username not in self._users:
            raise AppError("user_not_found", "用户不存在", 404)
        return self._users[username]

    def _principal_from_claims(self, payload: Mapping[str, Any]) -> Principal:
        """把令牌载荷转换为兼容旧接口的主体摘要。"""
        try:
            return Principal(
                user_id=UUID(str(payload["sub"])),
                username=str(payload["username"]),
                roles=frozenset(payload.get("roles", [])),
                org_scope=frozenset(payload.get("org_scope", [])),
                permission_version=int(payload.get("permission_version", 1)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError("invalid_token", "认证令牌无效", 401) from exc

    def _record_audit(
        self,
        action: str,
        username: str,
        actor_id: UUID | None,
        client_ip: str | None,
    ) -> None:
        """写入脱敏认证审计，用户名只保留不可逆摘要。"""
        username_hash = sha256(username.encode("utf-8")).hexdigest() if username else None
        self.audit_events.append(
            AuthAuditEvent(action, username_hash, actor_id, datetime.now(UTC), client_ip)
        )


auth_service = InMemoryAuthService()


async def login_user(command: LoginCommand, client_ip: str | None = None) -> AuthToken:
    """登录入口，委托认证服务签发 JWT。"""
    return auth_service.authenticate(command, client_ip=client_ip)


async def logout(token: str) -> None:
    """模块级退出入口，便于路由和任务统一复用。"""
    await auth_service.logout(token)
