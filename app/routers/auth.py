"""认证 API 路由。"""

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_principal
from app.schemas.auth import AuthToken, LoginCommand, Principal
from app.services.auth_service import login_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=AuthToken)
async def login(command: LoginCommand) -> AuthToken:
    """提交账号密码并返回令牌；当前未配置认证服务时返回 503。"""
    return await login_user(command)


@router.get("/me", response_model=Principal)
async def me(principal: Principal = Depends(get_current_principal)) -> Principal:
    """返回当前主体，不暴露密码或完整用户对象。"""
    return principal
