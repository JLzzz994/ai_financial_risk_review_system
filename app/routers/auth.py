"""认证 API 路由。"""

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.dependencies.auth import get_current_principal
from app.schemas.auth import AuthToken, LoginCommand, Principal
from app.services.auth_service import auth_service, login_user
from app.services.postgres_auth_service import postgres_auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=AuthToken)
async def login(
    command: LoginCommand,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthToken:
    """提交账号密码并返回短期令牌；认证依赖不可用时失败关闭。"""
    client_ip = request.client.host if request.client else None
    if settings.auth_backend == "postgres":
        return await postgres_auth_service.authenticate(session, command, client_ip=client_ip)
    return await login_user(command, client_ip=client_ip)


@router.get("/me", response_model=Principal)
async def me(principal: Principal = Depends(get_current_principal)) -> Principal:
    """返回当前主体，不暴露密码或完整用户对象。"""
    return principal


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    authorization: str | None = Header(default=None),
    _principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """撤销当前 Bearer 令牌；重复退出保持幂等。"""
    if not authorization or not authorization.startswith("Bearer "):
        # 依赖通常已经拦截，此处只为类型和未来自定义依赖保底。
        from app.errors import AppError

        raise AppError("missing_token", "缺少认证令牌", 401)
    token = authorization.removeprefix("Bearer ").strip()
    if settings.auth_backend == "postgres":
        await postgres_auth_service.logout(token)
    else:
        await auth_service.logout(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
