"""异步分析任务和 SSE 事件契约。"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class StartAnalysisCommand(BaseModel):
    """创建分析任务时绑定的不可变单据版本。"""

    document_version_id: UUID


class AnalysisStage(StrEnum):
    """分析流水线阶段。"""

    QUEUED = "queued"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    AGGREGATING = "aggregating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"


class AnalysisTaskResponse(BaseModel):
    """前端任务进度和恢复所需的稳定状态。"""

    task_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    document_version_id: UUID
    stage: AnalysisStage = AnalysisStage.QUEUED
    progress: int = Field(default=0, ge=0, le=100)
    retry_count: int = Field(default=0, ge=0)
    error_message: str | None = None
    manual_takeover: bool = False
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


class AnalysisEventType(StrEnum):
    """SSE 事件类型。"""

    PROGRESS = "progress"
    RESULT = "result"
    ERROR = "error"


class AnalysisEvent(BaseModel):
    """可断点重放的单个任务事件。"""

    event_id: int = Field(ge=1)
    type: AnalysisEventType
    task_id: UUID
    step: str
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
