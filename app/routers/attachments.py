"""单据附件接口，业务层只依赖 FileStorage。"""

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.services.attachment_service import AttachmentService
from engines.common.local_storage import LocalFileStorage

router = APIRouter(prefix="/api/v1/documents/{document_id}/attachments", tags=["attachments"])


class AttachmentResponse(BaseModel):
    """附件接口响应，不暴露本地绝对路径。"""

    attachment_id: UUID
    object_key: str
    size: int
    content_type: str
    parse_status: str


def get_attachment_service() -> AttachmentService:
    """构造开发环境附件服务，生产环境由依赖注入替换为 MinIO。"""
    return AttachmentService(LocalFileStorage(Path("var/uploads")))


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(document_id: UUID, file: UploadFile = File(...)) -> AttachmentResponse:
    """上传附件并执行大小、扩展名和对象键安全校验。"""
    del document_id
    extension = Path(file.filename or "").suffix.lower()
    content = await file.read()
    try:
        result = get_attachment_service().upload(
            f"attachments/{uuid4()}{extension}", content, file.content_type or "application/octet-stream", extension
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AttachmentResponse(
        attachment_id=uuid4(),
        object_key=result.object_key,
        size=result.size,
        content_type=result.content_type,
        parse_status=result.parse_status,
    )
