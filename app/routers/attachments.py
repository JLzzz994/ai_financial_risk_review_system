"""单据附件接口，业务层只依赖 FileStorage。"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.dependencies.auth import get_current_principal
from app.schemas.auth import Principal
from app.services.attachment_service import AttachmentRecord, AttachmentService
from app.services.persistent_attachment_service import PersistentAttachmentService
from engines.common.local_storage import LocalFileStorage
from engines.common.minio_storage import MinioFileStorage

router = APIRouter(prefix="/api/v1/documents/{document_id}/attachments", tags=["attachments"])
direct_router = APIRouter(prefix="/api/v1/attachments", tags=["attachments"])
_attachments: dict[UUID, "AttachmentResponse"] = {}


class AttachmentResponse(BaseModel):
    """附件接口响应，不暴露本地绝对路径。"""

    attachment_id: UUID
    file_name: str
    file_size: int
    mime_type: str
    storage_status: str
    parse_status: str
    required_kind: str | None = None
    uploaded_by: str
    uploaded_at: datetime
    # 兼容旧版调用方，生产前端只使用上面的标准字段。
    object_key: str | None = None
    size: int | None = None
    content_type: str | None = None


def get_attachment_service() -> AttachmentService:
    """构造开发环境附件服务，生产环境改走持久化服务。"""
    return AttachmentService(LocalFileStorage(Path(settings.local_storage_path)))


def get_persistent_attachment_service() -> PersistentAttachmentService:
    """构造生产附件服务，MinIO SDK 只在适配器内部加载。"""
    storage = MinioFileStorage.from_settings(
        settings.minio_endpoint,
        settings.minio_access_key,
        settings.minio_secret_key,
        settings.minio_bucket,
        settings.minio_secure,
    )
    return PersistentAttachmentService(storage)


async def _principal_if_persistent(
    authorization: str | None,
    session: AsyncSession,
) -> Principal:
    """生产后端分支手动触发认证，保持内存开发接口兼容。"""
    if settings.document_backend != "postgres":
        raise RuntimeError("仅 PostgreSQL 附件后端需要认证主体")
    return await get_current_principal(authorization, session)


def _response_from_record(record: AttachmentRecord) -> AttachmentResponse:
    """转换领域附件对象为前端契约。"""
    return AttachmentResponse(
        attachment_id=record.attachment_id,
        file_name=record.file_name,
        file_size=record.file_size,
        mime_type=record.mime_type,
        storage_status=record.storage_status,
        parse_status=record.parse_status,
        required_kind=record.required_kind,
        uploaded_by=str(record.uploaded_by),
        uploaded_at=record.uploaded_at,
        object_key=record.object_key,
        size=record.file_size,
        content_type=record.mime_type,
    )


@router.get("", response_model=list[AttachmentResponse])
async def list_attachments(
    document_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[AttachmentResponse]:
    """按数据范围列出单据附件。"""
    if settings.document_backend != "postgres":
        return [item for item in _attachments.values() if item.object_key]
    principal = await _principal_if_persistent(authorization, session)
    service = get_persistent_attachment_service()
    owner_id = await service.repository.get_document_applicant(session, document_id)
    if owner_id != principal.user_id and not principal.roles.intersection({"approver", "finance"}):
        raise HTTPException(status_code=403, detail="无权访问该单据附件")
    records = await service.list_attachments(session, document_id)
    return [_response_from_record(record) for record in records]


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    document_id: UUID,
    file: UploadFile = File(...),
    document_version_id: UUID | None = Query(default=None),
    required_kind: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> AttachmentResponse:
    """上传附件并执行扩展名、MIME、文件头、病毒和版本校验。"""
    extension = Path(file.filename or "").suffix.lower()
    content = await file.read()
    if settings.document_backend != "postgres":
        try:
            result = get_attachment_service().upload(
                f"attachments/{uuid4()}{extension}",
                content,
                file.content_type or "application/octet-stream",
                extension,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        attachment_id = uuid4()
        response = AttachmentResponse(
            attachment_id=attachment_id,
            file_name=Path(file.filename or "附件").name,
            file_size=result.size,
            mime_type=result.content_type,
            storage_status="stored",
            parse_status=result.parse_status,
            uploaded_by="development",
            uploaded_at=datetime.now(UTC),
            object_key=result.object_key,
            size=result.size,
            content_type=result.content_type,
        )
        _attachments[attachment_id] = response
        return response

    if document_version_id is None:
        raise HTTPException(status_code=422, detail="生产附件必须绑定 document_version_id")
    principal = await _principal_if_persistent(authorization, session)
    service = get_persistent_attachment_service()
    context = await service.repository.get_version_context(
        session, document_id, document_version_id
    )
    if context is None:
        raise HTTPException(status_code=404, detail="单据版本不存在")
    document_status, owner_id = context
    if principal.user_id != owner_id:
        raise HTTPException(status_code=403, detail="只能上传本人单据附件")
    try:
        record = await service.upload_attachment(
            session,
            document_id=document_id,
            document_version_id=document_version_id,
            file_name=file.filename or "附件",
            content=content,
            content_type=file.content_type or "application/octet-stream",
            actor_id=principal.user_id,
            document_status=document_status,
            required_kind=required_kind,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _response_from_record(record)


@router.get("/{attachment_id}", response_model=AttachmentResponse)
async def get_attachment(
    document_id: UUID,
    attachment_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> AttachmentResponse:
    """查询附件元数据，不返回本地绝对路径。"""
    if settings.document_backend != "postgres":
        response = _attachments.get(attachment_id)
        if response is None:
            raise HTTPException(status_code=404, detail="附件不存在")
        return response
    principal = await _principal_if_persistent(authorization, session)
    service = get_persistent_attachment_service()
    try:
        record = await service.get_attachment(session, attachment_id, principal)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if record.document_id != document_id:
        raise HTTPException(status_code=404, detail="附件不存在")
    return _response_from_record(record)


@router.delete("/{attachment_id}", status_code=204)
async def delete_attachment(
    document_id: UUID,
    attachment_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> None:
    """删除附件元数据和对象；已提交版本不可删除。"""
    if settings.document_backend != "postgres":
        response = _attachments.pop(attachment_id, None)
        if response is None:
            raise HTTPException(status_code=404, detail="附件不存在")
        get_attachment_service().storage.delete(response.object_key or "")
        return
    principal = await _principal_if_persistent(authorization, session)
    service = get_persistent_attachment_service()
    try:
        record = await service.get_attachment(session, attachment_id, principal)
        if record.document_id != document_id:
            raise HTTPException(status_code=404, detail="附件不存在")
        context = await service.repository.get_version_context(
            session, record.document_id, record.document_version_id
        )
        if context is None:
            raise HTTPException(status_code=404, detail="单据版本不存在")
        await service.delete_attachment(session, attachment_id, principal, context[0])
    except HTTPException:
        raise
    except (KeyError, PermissionError, ValueError) as exc:
        code = 403 if isinstance(exc, PermissionError) else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("/{attachment_id}/parse", response_model=AttachmentResponse)
async def parse_attachment(
    document_id: UUID | None,
    attachment_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> AttachmentResponse:
    """触发解析任务；任务只携带附件 ID、版本 ID 和幂等键。"""
    normalized_idempotency_key = idempotency_key.strip() if idempotency_key else ""
    if settings.document_backend != "postgres":
        response = _attachments.get(attachment_id)
        if response is None:
            raise HTTPException(status_code=404, detail="附件不存在")
        if not normalized_idempotency_key:
            raise HTTPException(status_code=422, detail="缺少有效的 Idempotency-Key")
        from app.tasks.attachment_tasks import parse_attachment_task

        try:
            parse_attachment_task(attachment_id, normalized_idempotency_key)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return response
    principal = await _principal_if_persistent(authorization, session)
    service = get_persistent_attachment_service()
    try:
        record = await service.get_attachment(session, attachment_id, principal)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if document_id is not None and record.document_id != document_id:
        raise HTTPException(status_code=404, detail="附件不存在")
    if not normalized_idempotency_key:
        raise HTTPException(status_code=422, detail="缺少有效的 Idempotency-Key")
    from app.tasks.attachment_tasks import parse_attachment_task

    try:
        parse_attachment_task(
            attachment_id,
            normalized_idempotency_key,
            document_version_id=record.document_version_id,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _response_from_record(record)


@direct_router.get("/{attachment_id}/download")
async def download_attachment(
    attachment_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """权限校验后重定向到五分钟内有效的对象地址。"""
    if settings.document_backend != "postgres":
        response = _attachments.get(attachment_id)
        if response is None:
            raise HTTPException(status_code=404, detail="附件不存在")
        url = get_attachment_service().storage.create_presigned_url(response.object_key or "")
        return RedirectResponse(url)
    principal = await _principal_if_persistent(authorization, session)
    service = get_persistent_attachment_service()
    try:
        url = await service.create_download_url(session, attachment_id, principal)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return RedirectResponse(url)


@direct_router.get("/{attachment_id}/preview")
async def preview_attachment(
    attachment_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """预览与下载共用权限和短期 URL 策略。"""
    return await download_attachment(attachment_id, authorization, session)


@direct_router.get("/{attachment_id}/parse-status", response_model=AttachmentResponse)
async def parse_status(
    attachment_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> AttachmentResponse:
    """查询解析状态和脱敏错误信息。"""
    if settings.document_backend != "postgres":
        response = _attachments.get(attachment_id)
        if response is None:
            raise HTTPException(status_code=404, detail="附件不存在")
        return response
    principal = await _principal_if_persistent(authorization, session)
    service = get_persistent_attachment_service()
    try:
        record = await service.get_attachment(session, attachment_id, principal)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return _response_from_record(record)


@direct_router.post("/{attachment_id}/parse", response_model=AttachmentResponse)
async def parse_attachment_direct(
    attachment_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> AttachmentResponse:
    """兼容非嵌套路由，委托同一解析业务逻辑。"""
    return await parse_attachment(
        None,
        attachment_id,
        authorization,
        session,
        idempotency_key,
    )


__all__ = ["AttachmentResponse", "direct_router", "get_attachment_service", "router"]
