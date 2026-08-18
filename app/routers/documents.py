"""费用报销单主链路 API。"""

from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.dependencies.auth import get_current_principal
from app.schemas.documents import (
    CreateDocumentCommand,
    DocumentActionCommand,
    DocumentLineItemCommand,
    DocumentLineItemPatch,
    DocumentLineItemResponse,
    DocumentPage,
    DocumentResponse,
    DocumentSubmitCommand,
    DocumentVersionResponse,
    UpdateDocumentCommand,
)
from app.services.document_service import DocumentService
from app.services.persistent_document_service import PersistentDocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
service = DocumentService()
persistent_service = PersistentDocumentService()


@router.get("", response_model=DocumentPage)
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    document_type: str | None = None,
    document_status: str | None = None,
    keyword: str | None = None,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> DocumentPage:
    """按申请人范围分页查询单据。"""
    try:
        if settings.document_backend == "postgres":
            principal = await get_current_principal(authorization, session)
            return await persistent_service.list_documents(
                session,
                principal,
                page=page,
                page_size=page_size,
                document_type=document_type,
                document_status=document_status,
                keyword=keyword,
            )
        documents = [service.get(item_id) for item_id in service.repository.documents]
        return DocumentPage(items=documents, total=len(documents), page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> DocumentResponse:
    """查询单据当前状态。"""
    try:
        if settings.document_backend == "postgres":
            principal = await get_current_principal(authorization, session)
            return await persistent_service.get(session, principal, document_id)
        return service.get(document_id)
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
            principal = await get_current_principal(authorization, session)
            return await persistent_service.create_draft(session, principal, command)
        return service.create_draft(command)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    command: UpdateDocumentCommand,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> DocumentResponse:
    """编辑草稿或退回单据，使用乐观锁。"""
    del idempotency_key
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=503, detail="草稿持久化未启用")
    try:
        principal = await get_current_principal(authorization, session)
        return await persistent_service.update_draft(session, principal, document_id, command)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{document_id}/copy", response_model=DocumentResponse, status_code=201)
async def copy_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> DocumentResponse:
    """复制本人单据为新草稿。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=503, detail="复制持久化未启用")
    try:
        principal = await get_current_principal(authorization, session)
        return await persistent_service.copy(session, principal, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{document_id}/submit", response_model=DocumentVersionResponse)
async def submit_document(
    document_id: UUID,
    command: DocumentSubmitCommand | None = Body(default=None),
    actor_id: UUID | None = None,
    expected_state_version: int = 1,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> DocumentVersionResponse:
    """提交单据并创建不可变版本。"""
    resolved = command or DocumentSubmitCommand(expected_state_version=expected_state_version)
    try:
        if settings.document_backend == "postgres":
            principal = await get_current_principal(authorization, session)
            version = await persistent_service.submit(
                session, principal, document_id, resolved.expected_state_version
            )
        else:
            if actor_id is None:
                raise ValueError("缺少 actor_id")
            version = service.submit(document_id, actor_id, resolved.expected_state_version)
        return DocumentVersionResponse(
            version_id=version.version_id,
            document_id=version.document_id,
            version_no=version.version_no,
            created_by=version.created_by,
            document_version_id=version.version_id,
            status="pending_review",
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{document_id}/withdraw", status_code=204)
async def withdraw_document(
    document_id: UUID,
    command: DocumentActionCommand,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> Response:
    """撤回尚未完成审批的单据。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=503, detail="撤回持久化未启用")
    try:
        principal = await get_current_principal(authorization, session)
        await persistent_service.change_status(
            session, principal, document_id, command, "withdrawn"
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/{document_id}/void", status_code=204)
async def void_document(
    document_id: UUID,
    command: DocumentActionCommand,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> Response:
    """作废符合条件的本人单据。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=503, detail="作废持久化未启用")
    try:
        principal = await get_current_principal(authorization, session)
        await persistent_service.change_status(session, principal, document_id, command, "voided")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> list[DocumentVersionResponse]:
    """查询单据版本历史。"""
    try:
        if settings.document_backend == "postgres":
            principal = await get_current_principal(authorization, session)
            return await persistent_service.list_versions(session, principal, document_id)
        return service.list_versions(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{document_id}/line-items", response_model=list[DocumentLineItemResponse])
async def list_line_items(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> list[DocumentLineItemResponse]:
    """查询单据明细。"""
    if settings.document_backend != "postgres":
        return []
    principal = await get_current_principal(authorization, session)
    try:
        return await persistent_service.list_line_items(session, principal, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{document_id}/line-items", response_model=DocumentLineItemResponse, status_code=201)
async def add_line_item(
    document_id: UUID,
    item: DocumentLineItemCommand,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> DocumentLineItemResponse:
    """新增单据明细。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=503, detail="明细持久化未启用")
    principal = await get_current_principal(authorization, session)
    try:
        return await persistent_service.add_line_item(session, principal, document_id, item)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{document_id}/line-items/{item_id}", response_model=DocumentLineItemResponse)
async def update_line_item(
    document_id: UUID,
    item_id: UUID,
    patch: DocumentLineItemPatch,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> DocumentLineItemResponse:
    """更新单据明细。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=503, detail="明细持久化未启用")
    principal = await get_current_principal(authorization, session)
    try:
        return await persistent_service.update_line_item(
            session, principal, document_id, item_id, patch
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{document_id}/line-items/{item_id}", status_code=204)
async def delete_line_item(
    document_id: UUID,
    item_id: UUID,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> Response:
    """删除单据明细。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=503, detail="明细持久化未启用")
    principal = await get_current_principal(authorization, session)
    try:
        await persistent_service.delete_line_item(session, principal, document_id, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)
