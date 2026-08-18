"""审批任务、固定顺序决定和审批历史 API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.dependencies.auth import get_current_principal
from app.schemas.approval import (
    ApprovalDecisionCommand,
    ApprovalDecisionResponse,
    ApprovalHistoryNode,
    ApprovalTaskPage,
    ApprovalTaskResponse,
)
from app.schemas.auth import PermissionCode
from app.services.approval_service import ApprovalService
from app.services.permission_service import authorize
from app.services.persistent_approval_service import PersistentApprovalService

router = APIRouter(prefix="/api/v1/approval-tasks", tags=["approval"])
history_router = APIRouter(prefix="/api/v1", tags=["approval"])
service = ApprovalService()
persistent_service = PersistentApprovalService()


@router.get("", response_model=ApprovalTaskPage)
async def list_approval_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    task_status: str | None = None,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> ApprovalTaskPage:
    """查询当前审批人被分配的任务。"""
    if settings.document_backend != "postgres":
        return ApprovalTaskPage(items=[], page=page, page_size=page_size, total=0)
    principal = await get_current_principal(authorization, session)
    authorize(principal, PermissionCode.APPROVAL_READ_ASSIGNED)
    return await persistent_service.list_tasks(
        session,
        principal,
        page=page,
        page_size=page_size,
        task_status=task_status,
    )


@router.get("/{task_id}", response_model=ApprovalTaskResponse)
async def get_approval_task(
    task_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> ApprovalTaskResponse:
    """查询当前审批人可见的任务详情。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=404, detail="审批任务不存在")
    principal = await get_current_principal(authorization, session)
    authorize(principal, PermissionCode.APPROVAL_READ_ASSIGNED)
    try:
        return await persistent_service.get_task(session, task_id, principal)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{task_id}/decision", response_model=ApprovalDecisionResponse)
async def submit_decision(
    task_id: UUID,
    command: ApprovalDecisionCommand,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> ApprovalDecisionResponse:
    """提交审批决定，最终结果不由 AI 自动触发。"""
    comment = command.resolved_comment
    request_key = idempotency_key or command.idempotency_key
    try:
        if settings.document_backend == "postgres":
            principal = await get_current_principal(authorization, session)
            authorize(principal, PermissionCode.APPROVAL_DECIDE)
            return await persistent_service.decide(
                session,
                task_id,
                principal,
                command.decision,
                comment,
                request_key,
            )
        if command.approver_id is None:
            raise ValueError("缺少 approver_id")
        return await service.decide(
            task_id,
            command.approver_id,
            command.decision,
            comment,
            request_key,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@history_router.get(
    "/documents/{document_id}/approval-history", response_model=list[ApprovalHistoryNode]
)
async def get_approval_history(
    document_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[ApprovalHistoryNode]:
    """查询单据的固定顺序审批历史。"""
    if settings.document_backend != "postgres":
        return []
    principal = await get_current_principal(authorization, session)
    authorize(principal, PermissionCode.APPROVAL_READ_ASSIGNED)
    return await persistent_service.history(session, document_id, principal)


__all__ = ["history_router", "router"]
