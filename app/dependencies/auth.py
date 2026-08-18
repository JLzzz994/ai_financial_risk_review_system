"""请求认证和功能权限依赖。"""

from collections.abc import Callable

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.errors import AppError
from app.schemas.auth import PermissionCode, Principal
from app.services.auth_service import auth_service
from app.services.permission_service import authorize
from app.services.postgres_auth_service import postgres_auth_service

_session_dependency = Depends(get_session)


async def get_current_principal(
    authorization: str | None = Header(default=None),
    session: AsyncSession = _session_dependency,
) -> Principal:
    """校验 Bearer 头、撤销状态、用户状态和权限版本。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError("missing_token", "缺少认证令牌", 401)
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise AppError("missing_token", "缺少认证令牌", 401)
    if settings.auth_backend == "postgres":
        return await postgres_auth_service.get_current_principal(session, token)
    return await auth_service.get_current_principal(token)


def require_permission(permission: PermissionCode | str) -> Callable[..., object]:
    """构造路由依赖，先完成认证再检查功能权限。"""

    current_principal_dependency = Depends(get_current_principal)
    required_permission = PermissionCode(permission)

    async def dependency(principal: Principal = current_principal_dependency) -> Principal:
        """校验当前主体是否拥有指定功能权限。"""
        authorize(principal, required_permission)
        return principal
    return dependency


get_current_user = get_current_principal
