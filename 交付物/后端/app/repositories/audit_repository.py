"""审计事件仓储契约。"""

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel


class AuditEvent(BaseModel):
    """不包含敏感原文的审计事件。"""

    actor_id: UUID | None = None
    action: str
    resource_type: str
    resource_id: UUID | None = None
    result: str = "success"
    request_id: str = ""
    occurred_at: datetime = datetime.now(UTC)


class AuditRepository(Protocol):
    """审计事件持久化接口。"""

    async def append(self, event: AuditEvent) -> None:
        """追加不可变审计事件。"""
