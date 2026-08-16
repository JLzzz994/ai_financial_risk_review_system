"""审核报告模型。"""

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ReportStatus(StrEnum):
    """报告状态。"""

    DRAFT = "draft"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ReviewReport(BaseModel):
    """绑定单据版本的不可变报告。"""

    report_id: UUID = Field(default_factory=uuid4)
    document_version_id: UUID
    status: ReportStatus
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReportListItem(BaseModel):
    """报告列表摘要。"""

    report_id: UUID
    document_version_id: UUID
    status: ReportStatus
    created_at: datetime
