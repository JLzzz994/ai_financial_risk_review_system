"""风险评估 API。"""

from uuid import UUID

from fastapi import APIRouter

from app.schemas.risk import RiskEvaluationInput, RiskEvaluationResponse
from app.services.risk_service import RiskService

router = APIRouter(prefix="/api/v1/document-versions/{document_version_id}/risk", tags=["risk"])
service = RiskService()


@router.post("/evaluate", response_model=RiskEvaluationResponse)
async def evaluate_risk(document_version_id: UUID, data: RiskEvaluationInput) -> RiskEvaluationResponse:
    """执行风险规则，不改变审批状态。"""
    return service.evaluate(document_version_id, data)
