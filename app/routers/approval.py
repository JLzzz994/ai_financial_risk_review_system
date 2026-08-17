"""审批任务 API。"""

from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from app.schemas.approval import ApprovalDecisionCommand, ApprovalDecisionResponse
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/api/v1/approval-tasks", tags=["approval"])
service = ApprovalService()


@router.post("/{task_id}/decision", response_model=ApprovalDecisionResponse)
async def submit_decision(
    task_id: UUID,
    command: ApprovalDecisionCommand,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ApprovalDecisionResponse:
    """提交审批决定，最终结果不由 AI 自动触发。"""
    try:
        return await service.decide(
            task_id,
            command.approver_id,
            command.decision,
            command.comment,
            idempotency_key or command.idempotency_key,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
