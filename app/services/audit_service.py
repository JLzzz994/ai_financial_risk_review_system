"""审计事件服务。"""

from datetime import UTC, datetime
from uuid import UUID

from app.repositories.audit_repository import AuditEvent


class AuditService:
    """追加不可变审计事件，不保存敏感原文。"""

    def __init__(self) -> None:
        """初始化内存事件列表。"""
        self.events: list[AuditEvent] = []

    def record(
        self,
        actor_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
    ) -> AuditEvent:
        """记录审批、复核、外部调用和敏感下载事件。"""
        event = AuditEvent(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            occurred_at=datetime.now(UTC),
        )
        self.events.append(event)
        return event
