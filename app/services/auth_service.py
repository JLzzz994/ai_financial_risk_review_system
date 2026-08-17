"""认证用例服务。"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher

from app.config import get_settings
from app.errors import AppError
from app.schemas.auth import AuthToken, LoginCommand, Principal, RoleCode

_password_hasher = PasswordHasher()


class InMemoryAuthService:
    """开发和测试使用的认证服务，生产环境替换为数据库仓储。"""

    def __init__(self) -> None:
        """初始化用户凭据和权限版本。"""
        self._users: dict[str, tuple[Principal, str]] = {}

    def register(self, username: str, password: str, role: RoleCode = RoleCode.APPLICANT) -> Principal:
        """注册测试用户并使用 Argon2id 保存密码哈希。"""
        principal = Principal(user_id=UUID(int=len(self._users) + 1), username=username, roles=frozenset({role}))
        self._users[username] = (principal, _password_hasher.hash(password))
        return principal

    def authenticate(self, command: LoginCommand) -> AuthToken:
        """校验密码并签发 30 分钟 JWT。"""
        if command.username not in self._users:
            raise AppError("invalid_credentials", "用户名或密码错误", 401)
        principal, password_hash = self._users[command.username]
        try:
            _password_hasher.verify(password_hash, command.password)
        except Exception as exc:
            raise AppError("invalid_credentials", "用户名或密码错误", 401) from exc
        now = datetime.now(UTC)
        payload = {"sub": str(principal.user_id), "username": principal.username, "roles": list(principal.roles), "permission_version": principal.permission_version, "iss": get_settings().jwt_issuer, "iat": now, "exp": now + timedelta(minutes=30)}
        return AuthToken(access_token=jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256"))

    def decode(self, token: str) -> Principal:
        """验证 JWT 签名、签发者和权限版本载荷。"""
        try:
            payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"], issuer=get_settings().jwt_issuer)
            return Principal(user_id=UUID(payload["sub"]), username=payload["username"], roles=frozenset(payload.get("roles", [])), permission_version=int(payload.get("permission_version", 1)))
        except Exception as exc:
            raise AppError("invalid_token", "认证令牌无效", 401) from exc


auth_service = InMemoryAuthService()


async def login_user(command: LoginCommand) -> AuthToken:
    """登录入口，委托认证服务签发 JWT。"""
    return auth_service.authenticate(command)
