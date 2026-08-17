"""审核会话服务。"""

from uuid import UUID, uuid4

from app.schemas.sessions import SessionMessage, SessionResponse, SessionStatus


class SessionService:
    """管理审核会话，不允许直接修改审批状态。"""

    def create(self, document_version_id: UUID) -> SessionResponse:
        """为单据版本创建会话。"""
        return SessionResponse(
            session_id=uuid4(),
            document_version_id=document_version_id,
            status=SessionStatus.OPEN,
            assistant_message="会话已创建",
        )

    def handle_message(
        self, session_id: UUID, document_version_id: UUID, message: SessionMessage
    ) -> SessionResponse:
        """处理会话消息并返回人工可确认的辅助结果。"""
        del session_id
        return SessionResponse(
            session_id=uuid4(),
            document_version_id=document_version_id,
            status=SessionStatus.WAITING_HUMAN,
            assistant_message=f"已记录：{message.content[:80]}",
        )
