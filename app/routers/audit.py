"""审计日志 API。"""

from fastapi import APIRouter

from app.repositories.audit_repository import AuditEvent
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])
service = AuditService()


@router.get("", response_model=list[AuditEvent])
async def list_audit_events() -> list[AuditEvent]:
    """返回当前授权范围内的审计事件。"""
    return list(service.events)
