"""认证用例服务。"""

from app.errors import AppError
from app.schemas.auth import AuthToken, LoginCommand


async def login_user(command: LoginCommand) -> AuthToken:
    """登录入口；未配置真实凭据校验时安全失败，不返回伪造令牌。"""
    del command
    raise AppError("auth_unavailable", "认证服务尚未配置", 503)
