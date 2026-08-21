"""审计日志 API 模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """审计日志列表项。"""

    log_id: UUID
    occurred_at: datetime
    actor_id: UUID | None = None
    actor_name: str = "系统"
    action: str
    resource_type: str
    resource_id: UUID | None = None
    result: str = "success"
    request_id: str = ""
    detail: str | None = None


class AuditLogPage(BaseModel):
    """审计日志分页响应。"""

    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
