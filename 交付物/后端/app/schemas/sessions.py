"""审核会话和分析任务模型。"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class SessionStatus(StrEnum):
    """会话状态。"""

    OPEN = "open"
    WAITING_ANALYSIS = "waiting_analysis"
    WAITING_HUMAN = "waiting_human"
    CLOSED = "closed"


class SessionMessage(BaseModel):
    """会话消息。"""

    content: str = Field(min_length=1, max_length=4000)
    intent: str | None = Field(default=None, max_length=64)


class CreateSessionCommand(BaseModel):
    """创建审核会话请求。"""

    document_id: UUID | None = None
    document_version_id: UUID | None = None


class CloseSessionCommand(BaseModel):
    """关闭审核会话请求。"""

    reason: str = Field(min_length=1, max_length=500)


class SessionMessageResponse(BaseModel):
    """会话消息响应。"""

    message_id: UUID
    role: str
    content: str
    message_type: str
    created_at: datetime


class SessionResponse(BaseModel):
    """会话响应。"""

    session_id: UUID
    document_id: UUID | None = None
    document_version_id: UUID
    status: SessionStatus
    assistant_message: str
    created_at: datetime | None = None
