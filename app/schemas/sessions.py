"""审核会话和分析任务模型。"""

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


class SessionResponse(BaseModel):
    """会话响应。"""

    session_id: UUID
    document_version_id: UUID
    status: SessionStatus
    assistant_message: str
