"""风险评估和人工复核 API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.dependencies.auth import get_current_principal
from app.schemas.risk import (
    ManualReviewRequest,
    ManualReviewResponse,
    RiskEvaluationInput,
    RiskEvaluationResponse,
    RiskReviewStatusRequest,
)
from app.services.manual_review_service import ManualReviewService
from app.services.persistent_risk_service import PersistentRiskService
from app.services.risk_service import RiskService
from engines.risk.contracts import RiskFinding

router = APIRouter(prefix="/api/v1/document-versions/{document_version_id}/risk", tags=["risk"])
service = RiskService()
manual_review_service = ManualReviewService()
persistent_service = PersistentRiskService()


@router.post("/evaluate", response_model=RiskEvaluationResponse)
async def evaluate_risk(
    document_version_id: UUID,
    data: RiskEvaluationInput,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> RiskEvaluationResponse:
    """执行风险规则，不改变审批状态。"""
    if settings.document_backend == "postgres":
        await get_current_principal(authorization, session)
        findings = await persistent_service.evaluate(session, document_version_id, data)
        return RiskEvaluationResponse(document_version_id=document_version_id, findings=findings)
    return service.evaluate(document_version_id, data)


@router.post("/manual-reviews/{review_id}", response_model=ManualReviewResponse)
async def update_manual_review(
    document_version_id: UUID,
    review_id: UUID,
    data: ManualReviewRequest,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> ManualReviewResponse:
    """由审核人员更新复核状态，不改变审批状态。"""
    if settings.document_backend == "postgres":
        principal = await get_current_principal(authorization, session)
        if principal.user_id != data.reviewer_id:
            raise HTTPException(status_code=403, detail="只能由当前审核人员提交复核")
        if not data.comment.strip():
            raise HTTPException(status_code=422, detail="人工复核必须填写处理意见")
        try:
            actual_version_id = await persistent_service.get_version_id(session, review_id)
            if actual_version_id != document_version_id:
                raise ValueError("风险项不存在")
            finding = await persistent_service.review(
                session, review_id, data.status, data.evidence
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return ManualReviewResponse(
            review_id=review_id,
            document_version_id=document_version_id,
            status=finding.status,
            reviewer_id=principal.user_id,
            comment=data.comment,
        )
    try:
        record = manual_review_service.update_review_status(
            review_id, data.reviewer_id, data.status, data.comment, data.evidence
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ManualReviewResponse(
        review_id=record.review_id,
        document_version_id=record.document_version_id,
        status=record.status,
        reviewer_id=record.reviewer_id,
        comment=record.comment,
    )


document_risk_router = APIRouter(prefix="/api/v1", tags=["risk"])


@document_risk_router.get(
    "/documents/{document_id}/risk-findings", response_model=list[RiskFinding]
)
async def list_document_risk_findings(
    document_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[RiskFinding]:
    """查询单据所有版本的风险项，供工作台和风险页使用。"""
    if settings.document_backend != "postgres":
        return []
    await get_current_principal(authorization, session)
    return await persistent_service.list_findings_by_document(session, document_id)


@document_risk_router.patch(
    "/risk-findings/{finding_id}/review-status", response_model=RiskFinding
)
async def patch_finding_review_status(
    finding_id: UUID,
    data: RiskReviewStatusRequest,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> RiskFinding:
    """按前端契约保存人工风险复核，不触碰审批状态。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=404, detail="风险项不存在")
    await get_current_principal(authorization, session)
    if not data.review_comment.strip():
        raise HTTPException(status_code=422, detail="人工复核必须填写处理意见")
    try:
        return await persistent_service.review(session, finding_id, data.review_status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
