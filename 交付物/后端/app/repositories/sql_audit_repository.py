"""审计日志 PostgreSQL 仓储。"""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extended import audit_logs, users
from app.schemas.audit import AuditLogPage, AuditLogResponse


class SqlAuditRepository:
    """追加并分页读取不可变审计日志。"""

    async def append(
        self,
        session: AsyncSession,
        actor_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        detail: dict[str, Any] | None = None,
        request_id: str = "",
    ) -> UUID:
        """写入审计日志，不保存敏感原文。"""
        log_id = uuid4()
        await session.execute(
            insert(audit_logs).values(
                id=log_id,
                user_id=actor_id,
                actor_id=actor_id,
                action_type=action,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail_json={**(detail or {}), "request_id": request_id},
                created_at=datetime.now(UTC),
            )
        )
        return log_id

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
        actor_user = users.alias("audit_actor")
        statement = (
            select(audit_logs, actor_user.c.display_name.label("actor_name"))
            .select_from(audit_logs)
            .outerjoin(actor_user, audit_logs.c.actor_id == actor_user.c.id)
            .order_by(audit_logs.c.created_at.desc())
        )
        if action:
            statement = statement.where(audit_logs.c.action.ilike(f"%{action}%"))
        if actor:
            statement = statement.where(actor_user.c.display_name.ilike(f"%{actor}%"))
        result = await session.execute(statement)
        rows = result.mappings().all()
        if request_id:
            rows = [
                row
                for row in rows
                if str((row["detail_json"] or {}).get("request_id", "")) == request_id
            ]
        total = len(rows)
        start = (page - 1) * page_size
        return AuditLogPage(
            items=[self._to_response(row) for row in rows[start : start + page_size]],
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def _to_response(row: Any) -> AuditLogResponse:
        """将审计表行转换为列表项。"""
        detail = row.get("detail_json") or {}
        return AuditLogResponse(
            log_id=row["id"],
            occurred_at=row["created_at"],
            actor_id=row.get("actor_id") or row.get("user_id"),
            actor_name=str(row.get("actor_name") or "系统"),
            action=str(row.get("action") or row["action_type"]),
            resource_type=str(row["resource_type"]),
            resource_id=row.get("resource_id"),
            result=str(detail.get("result", "success")),
            request_id=str(detail.get("request_id", "")),
            detail=json.dumps(detail, ensure_ascii=False) if detail else None,
        )


__all__ = ["SqlAuditRepository"]
