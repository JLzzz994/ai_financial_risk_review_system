"""请求认证依赖的最小实现。"""

from fastapi import Header, HTTPException, status

from app.schemas.auth import Principal


async def get_current_principal(authorization: str | None = Header(default=None)) -> Principal:
    """校验 Bearer 头；真实 JWT/Redis 校验由认证服务接入。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证令牌")
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="认证服务尚未配置")
