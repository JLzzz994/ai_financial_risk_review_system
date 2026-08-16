"""审批任务 API。"""

from uuid import UUID

from fastapi import APIRouter

from app.schemas.approval import ApprovalDecisionCommand, ApprovalDecisionResponse
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/api/v1/approval-tasks", tags=["approval"])
service = ApprovalService()


@router.post("/{task_id}/decision", response_model=ApprovalDecisionResponse)
async def submit_decision(task_id: UUID, command: ApprovalDecisionCommand) -> ApprovalDecisionResponse:
    """提交审批决定，最终结果不由 AI 自动触发。"""
    try:
        return service.submit_decision(task_id, command)
    except PermissionError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail=str(exc)) from exc
