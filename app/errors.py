"""统一错误模型与异常处理。"""

from collections.abc import Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """应用层可预期异常。"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        """保存错误码、非敏感提示和 HTTP 状态码。"""
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AuthorizationError(AppError):
    """权限不足或数据范围不匹配。"""

    def __init__(self, message: str = "无权执行该操作") -> None:
        """使用统一 403 错误码构造授权异常。"""
        super().__init__("forbidden", message, 403)


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """将应用异常转换为统一且不泄露敏感信息的 JSON 响应。"""
    error = exc if isinstance(exc, AppError) else AppError("internal_error", "服务器内部错误", 500)
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=error.status_code,
        content={
            "code": error.code,
            "message": error.message,
            "request_id": request_id,
            "details": error.details,
            # 保留旧客户端读取的嵌套错误结构，迁移期间不破坏已有契约。
            "error": {"code": error.code, "message": error.message},
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """将未捕获异常转换为不暴露堆栈的统一响应。"""
    return await app_error_handler(request, exc)


ErrorHandler = Callable[[Request, Exception], Any]
