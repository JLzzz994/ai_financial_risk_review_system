"""制度/规则依据检索 API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.dependencies.auth import get_current_principal
from app.errors import AppError
from app.providers import build_rag_provider_registry
from app.schemas.rag import RagEvidenceResponse, RagRetrieveRequest
from app.services.audit_service import AuditService
from app.services.persistent_audit_service import PersistentAuditService
from app.services.rag_service import RagService

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])
audit_service = AuditService()
persistent_audit_service = PersistentAuditService()


@router.post("/retrieve", response_model=list[RagEvidenceResponse])
async def retrieve_rag(
    data: RagRetrieveRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[RagEvidenceResponse]:
    """检索制度依据；只读，不改变风险或审批状态。"""
    principal = await get_current_principal(authorization, session)
    request_id = getattr(getattr(request, "state", None), "request_id", "")
    try:
        evidence = await RagService(build_rag_provider_registry()).retrieve(
            data.query,
            data.top_k,
            item_name=data.item_name,
        )
    except AppError as exc:
        await _record_audit(
            session,
            principal.user_id,
            request_id=request_id,
            result="error",
            error_code=exc.code,
        )
        raise
    await _record_audit(
        session,
        principal.user_id,
        request_id=request_id,
        result="success",
        result_count=len(evidence),
    )
    return [
        RagEvidenceResponse(
            chunk_id=item.chunk_id,
            content=item.content,
            source_title=item.source_title,
            score=item.score,
            rule_version=item.rule_version,
            page_or_location=item.page_or_location,
            item_name=item.item_name,
            metadata=item.metadata or {},
        )
        for item in evidence
    ]


async def _record_audit(
    session: AsyncSession,
    actor_id: UUID,
    *,
    request_id: str,
    result: str,
    result_count: int | None = None,
    error_code: str | None = None,
) -> None:
    """记录 RAG 调用，不写入查询全文、证据原文或连接信息。"""
    detail: dict[str, object] = {}
    detail["result"] = result
    if result_count is not None:
        detail["result_count"] = result_count
    if error_code is not None:
        detail["error_code"] = error_code
    if settings.document_backend == "postgres":
        await persistent_audit_service.record(
            session,
            actor_id,
            "rag.retrieve",
            "knowledge_base",
            detail=detail,
            request_id=request_id,
        )
        await session.commit()
        return
    audit_service.record(
        actor_id,
        "rag.retrieve",
        "knowledge_base",
        result=result,
        request_id=request_id,
    )


__all__ = ["router"]
