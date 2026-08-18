"""审计日志 PostgreSQL 服务。"""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.sql_audit_repository import SqlAuditRepository
from app.schemas.audit import AuditLogPage


class PersistentAuditService:
    """在业务事务中追加敏感操作审计。"""

    def __init__(self, repository: SqlAuditRepository | None = None) -> None:
        """注入审计仓储。"""
        self.repository = repository or SqlAuditRepository()

    async def record(
        self,
        session: AsyncSession,
        actor_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        detail: dict[str, Any] | None = None,
        request_id: str = "",
    ) -> UUID:
        """追加一条脱敏审计日志。"""
        return await self.repository.append(
            session, actor_id, action, resource_type, resource_id, detail, request_id
        )

    async def list(
        self,
        session: AsyncSession,
        *,
        page: int,
        page_size: int,
        action: str | None = None,
        actor: str | None = None,
        request_id: str | None = None,
    ) -> AuditLogPage:
        """分页查询审计日志。"""
        return await self.repository.list(
            session,
            page=page,
            page_size=page_size,
            action=action,
            actor=actor,
            request_id=request_id,
        )


__all__ = ["PersistentAuditService"]
