"""慧策·慧经营多平台电商对账异常审核 API。"""

from uuid import UUID

from fastapi import APIRouter

from app.schemas.reconciliation import ReconciliationEvaluationInput, ReconciliationEvaluationResponse
from app.services.reconciliation_service import ReconciliationService

router = APIRouter(
    prefix="/api/v1/document-versions/{document_version_id}/reconciliation",
    tags=["reconciliation"],
)
service = ReconciliationService()


@router.post("/evaluate", response_model=ReconciliationEvaluationResponse)
async def evaluate_reconciliation(
    document_version_id: UUID,
    data: ReconciliationEvaluationInput,
) -> ReconciliationEvaluationResponse:
    """执行电商对账确定性规则；结果不直接改变审批状态。"""
    return service.evaluate(document_version_id, data)
