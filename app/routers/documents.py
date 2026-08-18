"""费用报销单 API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.dependencies.auth import get_current_principal
from app.schemas.documents import CreateDocumentCommand, DocumentResponse, DocumentVersionResponse
from app.services.document_service import DocumentService
from app.services.persistent_document_service import PersistentDocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
service = DocumentService()
persistent_service = PersistentDocumentService()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> DocumentResponse:
    """查询单据当前状态。"""
    try:
        if settings.document_backend == "postgres":
            principal = await get_current_principal(authorization)
            return await persistent_service.get(session, principal, document_id)
        return service.get(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> list[DocumentVersionResponse]:
    """查询单据版本历史。"""
    try:
        if settings.document_backend == "postgres":
            principal = await get_current_principal(authorization)
            return await persistent_service.list_versions(session, principal, document_id)
        return service.list_versions(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=DocumentResponse, status_code=201)
async def create_document(
    command: CreateDocumentCommand,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> DocumentResponse:
    """创建费用报销草稿。"""
    try:
        if settings.document_backend == "postgres":
            principal = await get_current_principal(authorization)
            return await persistent_service.create_draft(session, principal, command)
        return service.create_draft(command)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{document_id}/submit", response_model=DocumentVersionResponse)
async def submit_document(
    document_id: UUID,
    actor_id: UUID | None = None,
    expected_state_version: int = 1,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> DocumentVersionResponse:
    """提交单据并创建不可变版本。"""
    try:
        if settings.document_backend == "postgres":
            principal = await get_current_principal(authorization)
            return await persistent_service.submit(
                session, principal, document_id, expected_state_version
            )
        if actor_id is None:
            raise HTTPException(status_code=422, detail="缺少 actor_id")
        return service.submit(document_id, actor_id, expected_state_version)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
