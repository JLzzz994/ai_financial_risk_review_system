"""审计日志 API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.dependencies.auth import get_current_principal
from app.schemas.audit import AuditLogPage, AuditLogResponse
from app.services.audit_service import AuditService
from app.services.persistent_audit_service import PersistentAuditService

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])
service = AuditService()
persistent_service = PersistentAuditService()


@router.get("", response_model=AuditLogPage)
async def list_audit_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    action: str | None = None,
    actor: str | None = None,
    request_id: str | None = None,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> AuditLogPage:
    """返回授权范围内的审计事件。"""
    if settings.document_backend == "postgres":
        principal = await get_current_principal(authorization, session)
        if "admin" not in {role.value for role in principal.roles}:
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="仅管理员可查看审计日志")
        return await persistent_service.list(
            session,
            page=page,
            page_size=page_size,
            action=action,
            actor=actor,
            request_id=request_id,
        )
    events = service.events
    items = [
        AuditLogResponse(
            log_id=UUID(int=index + 1),
            occurred_at=event.occurred_at,
            actor_id=event.actor_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            result=event.result,
            request_id=event.request_id,
        )
        for index, event in enumerate(events)
    ]
    start = (page - 1) * page_size
    return AuditLogPage(
        items=items[start : start + page_size],
        total=len(items),
        page=page,
        page_size=page_size,
    )


@router.get("/export")
async def export_audit_events(
    authorization: str | None = Header(default=None),
    _session: AsyncSession = Depends(get_session),
) -> Response:
    """导出脱敏审计日志 CSV。"""
    if settings.document_backend == "postgres":
        await get_current_principal(authorization)
    lines = ["log_id,occurred_at,action,resource_type,resource_id,request_id,result"]
    for event in service.events:
        lines.append(
            f"{event.resource_id or ''},{event.occurred_at.isoformat()},"
            f"{event.action},{event.resource_type},{event.resource_id or ''},"
            f"{event.request_id},{event.result}"
        )
    return Response(
        content="\n".join(lines).encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit-logs.csv"'},
    )
