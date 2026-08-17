"""审核会话 API。"""

from uuid import UUID

from fastapi import APIRouter

from app.schemas.sessions import SessionMessage, SessionResponse
from app.services.session_service import SessionService

router = APIRouter(prefix="/api/v1/review-sessions", tags=["review-sessions"])
service = SessionService()


@router.post("", response_model=SessionResponse)
async def create_session(document_version_id: UUID) -> SessionResponse:
    """创建绑定单据版本的审核会话。"""
    return service.create(document_version_id)


@router.post("/{session_id}/messages", response_model=SessionResponse)
async def send_message(
    session_id: UUID, document_version_id: UUID, message: SessionMessage
) -> SessionResponse:
    """发送审核消息，返回人工确认态辅助结果。"""
    return service.handle_message(session_id, document_version_id, message)
