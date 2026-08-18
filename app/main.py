"""FastAPI 应用入口与健康检查。"""

from fastapi import FastAPI

from app.config import settings
from app.errors import AppError, app_error_handler, unhandled_error_handler
from app.logging_config import configure_logging, get_logger, log_boundary
from app.middleware.request_context import RequestContextMiddleware
from app.routers.analysis import router as analysis_router
from app.routers.approval import router as approval_router
from app.routers.attachments import direct_router as direct_attachment_router
from app.routers.attachments import router as attachment_router
from app.routers.audit import router as audit_router
from app.routers.auth import router as auth_router
from app.routers.documents import router as documents_router
from app.routers.reports import router as reports_router
from app.routers.risk import document_risk_router
from app.routers.risk import router as risk_router
from app.routers.sessions import router as session_router
from app.services.health_service import get_readiness

configure_logging()
logger = get_logger(__name__)
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(RequestContextMiddleware)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)
app.include_router(auth_router)
app.include_router(analysis_router)
app.include_router(attachment_router)
app.include_router(direct_attachment_router)
app.include_router(session_router)
app.include_router(risk_router)
app.include_router(document_risk_router)
app.include_router(approval_router)
app.include_router(reports_router)
app.include_router(audit_router)
app.include_router(documents_router)


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    """返回进程存活状态。"""
    log_boundary(logger, "health_live", "enter")
    result = {"status": "ok"}
    log_boundary(logger, "health_live", "exit", status=result["status"])
    return result


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    """仅在 PostgreSQL 与 Redis 均可用时返回服务就绪。"""
    log_boundary(logger, "health_ready", "enter")
    readiness = await get_readiness()
    if readiness.status != "ready":
        from app.errors import AppError

        raise AppError(
            "service_not_ready",
            "基础依赖尚未就绪",
            503,
            details={"dependencies": readiness.dependencies.model_dump()},
        )
    result: dict[str, str] = {"status": readiness.status}
    log_boundary(logger, "health_ready", "exit", status=result["status"])
    return result
