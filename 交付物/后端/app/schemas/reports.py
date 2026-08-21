"""审核报告模型。"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
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
    document_id: UUID | None = None
    document_version_id: UUID
    version_no: int = 1
    status: ReportStatus = ReportStatus.DRAFT
    report_status: ReportStatus | None = None
    overall_risk_level: str | None = None
    rule_version: str = ""
    content: str | dict[str, Any]
    generated_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReportListItem(BaseModel):
    """报告列表摘要。"""

    report_id: UUID
    document_version_id: UUID
    status: ReportStatus
    report_status: ReportStatus | None = None
    overall_risk_level: str | None = None
    created_at: datetime


class ExportTaskResponse(BaseModel):
    """报告异步导出任务状态。"""

    export_task_id: UUID
    status: str
    file_name: str | None = None
    error_message: str | None = None


class ReportExportCommand(BaseModel):
    """报告导出请求。"""

    format: str = "pdf"
