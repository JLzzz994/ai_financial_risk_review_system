"""FastAPI 应用入口与健康检查。"""

from fastapi import FastAPI

from app.config import get_settings
from app.errors import AppError, app_error_handler, unhandled_error_handler
from app.logging_config import configure_logging, get_logger, log_boundary
from app.middleware.request_context import RequestContextMiddleware
from app.routers.auth import router as auth_router

configure_logging()
logger = get_logger(__name__)
app = FastAPI(title=get_settings().app_name, version="0.1.0")
app.add_middleware(RequestContextMiddleware)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)
app.include_router(auth_router)


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    """返回进程存活状态。"""
    log_boundary(logger, "health_live", "enter")
    result = {"status": "ok"}
    log_boundary(logger, "health_live", "exit", status=result["status"])
    return result


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    """返回服务就绪状态。"""
    log_boundary(logger, "health_ready", "enter")
    result = {"status": "ready"}
    log_boundary(logger, "health_ready", "exit", status=result["status"])
    return result
