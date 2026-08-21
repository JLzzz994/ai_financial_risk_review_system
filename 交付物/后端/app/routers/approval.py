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
    WorkflowCreateCommand,
    WorkflowPatchCommand,
    WorkflowPublishCommand,
    WorkflowTemplateResponse,
)
from app.schemas.auth import PermissionCode
from app.services.approval_service import ApprovalService
from app.services.permission_service import authorize
from app.services.persistent_approval_service import PersistentApprovalService
from app.services.persistent_workflow_service import PersistentWorkflowService

router = APIRouter(prefix="/api/v1/approval-tasks", tags=["approval"])
history_router = APIRouter(prefix="/api/v1", tags=["approval"])
workflow_router = APIRouter(prefix="/api/v1/approval-workflows", tags=["approval"])
service = ApprovalService()
persistent_service = PersistentApprovalService()
persistent_workflow_service = PersistentWorkflowService()


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


@workflow_router.get("", response_model=list[WorkflowTemplateResponse])
async def list_workflows(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[WorkflowTemplateResponse]:
    """管理员查询审批流程配置。"""
    if settings.document_backend != "postgres":
        return []
    principal = await get_current_principal(authorization, session)
    authorize(principal, PermissionCode.CONFIG_MANAGE, is_configuration_resource=True)
    return await persistent_workflow_service.list_workflows(session)


@workflow_router.post("", response_model=WorkflowTemplateResponse, status_code=201)
async def create_workflow(
    command: WorkflowCreateCommand,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> WorkflowTemplateResponse:
    """管理员创建顺序审批流程草稿。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=503, detail="流程配置持久化未启用")
    principal = await get_current_principal(authorization, session)
    authorize(principal, PermissionCode.CONFIG_MANAGE, is_configuration_resource=True)
    try:
        return await persistent_workflow_service.create(session, command)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@workflow_router.patch("/{workflow_id}", response_model=WorkflowTemplateResponse)
async def update_workflow(
    workflow_id: UUID,
    command: WorkflowPatchCommand,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> WorkflowTemplateResponse:
    """管理员更新草稿，已发布模板必须先停用或新建版本。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=503, detail="流程配置持久化未启用")
    principal = await get_current_principal(authorization, session)
    authorize(principal, PermissionCode.CONFIG_MANAGE, is_configuration_resource=True)
    try:
        return await persistent_workflow_service.update(session, workflow_id, command)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@workflow_router.post("/{workflow_id}/publish", response_model=WorkflowTemplateResponse)
async def publish_workflow(
    workflow_id: UUID,
    command: WorkflowPublishCommand,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> WorkflowTemplateResponse:
    """管理员发布流程，发布原因写入后续审计链路。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=503, detail="流程配置持久化未启用")
    principal = await get_current_principal(authorization, session)
    authorize(principal, PermissionCode.CONFIG_MANAGE, is_configuration_resource=True)
    try:
        return await persistent_workflow_service.publish(session, workflow_id, command.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


__all__ = ["history_router", "router", "workflow_router"]
