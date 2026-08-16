"""风险评估 API。"""

from uuid import UUID

from fastapi import APIRouter

from app.schemas.risk import (
    ManualReviewRequest,
    ManualReviewResponse,
    RiskEvaluationInput,
    RiskEvaluationResponse,
)
from app.services.manual_review_service import ManualReviewService
from app.services.risk_service import RiskService

router = APIRouter(prefix="/api/v1/document-versions/{document_version_id}/risk", tags=["risk"])
service = RiskService()
manual_review_service = ManualReviewService()


@router.post("/evaluate", response_model=RiskEvaluationResponse)
async def evaluate_risk(
    document_version_id: UUID, data: RiskEvaluationInput
) -> RiskEvaluationResponse:
    """执行风险规则，不改变审批状态。"""
    return service.evaluate(document_version_id, data)


@router.post("/manual-reviews/{review_id}", response_model=ManualReviewResponse)
async def update_manual_review(review_id: UUID, data: ManualReviewRequest) -> ManualReviewResponse:
    """由审核人员更新复核状态，不改变审批状态。"""
    record = manual_review_service.update_review_status(
        review_id,
        data.reviewer_id,
        data.status,
        data.comment,
        data.evidence,
    )
    return ManualReviewResponse(
        review_id=record.review_id,
        document_version_id=record.document_version_id,
        status=record.status,
        reviewer_id=record.reviewer_id,
        comment=record.comment,
    )
