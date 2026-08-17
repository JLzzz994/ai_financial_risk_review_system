"""请求认证依赖的最小实现。"""

from fastapi import Header, HTTPException, status

from app.schemas.auth import Principal
from app.services.auth_service import auth_service


async def get_current_principal(authorization: str | None = Header(default=None)) -> Principal:
    """校验 Bearer 头；真实 JWT/Redis 校验由认证服务接入。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证令牌")
    try:
        return auth_service.decode(authorization.removeprefix("Bearer ").strip())
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证令牌无效") from exc
