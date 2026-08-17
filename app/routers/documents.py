"""费用报销单 API。"""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.schemas.documents import CreateDocumentCommand, DocumentResponse, DocumentVersionResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
service = DocumentService()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: UUID) -> DocumentResponse:
    """查询单据当前状态。"""
    try:
        return service.get(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(document_id: UUID) -> list[DocumentVersionResponse]:
    """查询单据版本历史。"""
    try:
        return service.list_versions(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=DocumentResponse, status_code=201)
async def create_document(command: CreateDocumentCommand) -> DocumentResponse:
    """创建费用报销草稿。"""
    try:
        return service.create_draft(command)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{document_id}/submit", response_model=DocumentVersionResponse)
async def submit_document(
    document_id: UUID, actor_id: UUID, expected_state_version: int = 1
) -> DocumentVersionResponse:
    """提交单据并创建不可变版本。"""
    try:
        return service.submit(document_id, actor_id, expected_state_version)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
