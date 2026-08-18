"""审核会话和消息的 PostgreSQL 仓储。"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import DocumentVersion
from app.models.extended import review_sessions, session_messages
from app.schemas.sessions import SessionMessageResponse, SessionResponse, SessionStatus


class SqlSessionRepository:
    """保存会话轮次，不把会话状态当作单据事实源。"""

    async def resolve_version(
        self,
        session: AsyncSession,
        document_id: UUID | None,
        document_version_id: UUID | None,
    ) -> UUID:
        """解析会话绑定版本，缺省取单据最新版本。"""
        if document_version_id is not None:
            return document_version_id
        if document_id is None:
            raise ValueError("会话必须绑定 document_id 或 document_version_id")
        result = await session.execute(
            select(DocumentVersion.id)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_no.desc())
            .limit(1)
        )
        version_id = result.scalar_one_or_none()
        if version_id is None:
            raise ValueError("单据尚未提交版本")
        return UUID(str(version_id))

    async def create(
        self,
        session: AsyncSession,
        user_id: UUID,
        document_version_id: UUID,
    ) -> SessionResponse:
        """创建绑定版本的审核会话。"""
        context = await session.execute(
            select(DocumentVersion.document_id).where(DocumentVersion.id == document_version_id)
        )
        document_id = context.scalar_one_or_none()
        if document_id is None:
            raise ValueError("单据版本不存在")
        session_id = uuid4()
        now = datetime.now(UTC)
        await session.execute(
            insert(review_sessions).values(
                id=session_id,
                user_id=user_id,
                document_id=document_id,
                document_version_id=document_version_id,
                session_status="open",
                slot_state_json={},
                state_version=1,
                created_at=now,
                updated_at=now,
            )
        )
        return SessionResponse(
            session_id=session_id,
            document_id=document_id,
            document_version_id=document_version_id,
            status=SessionStatus.OPEN,
            assistant_message="会话已创建",
            created_at=now,
        )

    async def get(
        self, session: AsyncSession, session_id: UUID, user_id: UUID
    ) -> SessionResponse:
        """读取当前用户的会话。"""
        result = await session.execute(
            select(review_sessions).where(
                review_sessions.c.id == session_id,
                review_sessions.c.user_id == user_id,
            )
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("审核会话不存在")
        return self._to_response(row, "会话状态已恢复")

    async def add_message(
        self,
        session: AsyncSession,
        session_id: UUID,
        user_id: UUID,
        content: str,
        intent: str | None,
    ) -> list[SessionMessageResponse]:
        """追加用户消息和脱敏辅助回复。"""
        session_row = await session.execute(
            select(review_sessions).where(
                review_sessions.c.id == session_id,
                review_sessions.c.user_id == user_id,
            )
        )
        current = session_row.mappings().first()
        if current is None:
            raise ValueError("审核会话不存在")
        if current["session_status"] == "closed":
            raise ValueError("审核会话已关闭")
        now = datetime.now(UTC)
        await session.execute(
            insert(session_messages).values(
                id=uuid4(),
                session_id=session_id,
                role="user",
                content=content,
                message_type=intent or "chat",
                metadata_json={},
                created_at=now,
            )
        )
        assistant_content = f"已记录：{content[:80]}"
        await session.execute(
            insert(session_messages).values(
                id=uuid4(),
                session_id=session_id,
                role="assistant",
                content=assistant_content,
                message_type="assistant_hint",
                metadata_json={"intent": intent} if intent else {},
                created_at=now,
            )
        )
        await session.execute(
            update(review_sessions)
            .where(review_sessions.c.id == session_id)
            .values(
                session_status="waiting_human",
                updated_at=now,
                state_version=current["state_version"] + 1,
            )
        )
        return await self.list_messages(session, session_id, user_id)

    async def list_messages(
        self, session: AsyncSession, session_id: UUID, user_id: UUID
    ) -> list[SessionMessageResponse]:
        """按创建时间读取会话消息。"""
        exists = await session.execute(
            select(review_sessions.c.id).where(
                review_sessions.c.id == session_id,
                review_sessions.c.user_id == user_id,
            )
        )
        if exists.scalar_one_or_none() is None:
            raise ValueError("审核会话不存在")
        result = await session.execute(
            select(session_messages)
            .where(session_messages.c.session_id == session_id)
            .order_by(session_messages.c.created_at, session_messages.c.id)
        )
        return [
            SessionMessageResponse(
                message_id=row["id"],
                role=row["role"],
                content=row["content"],
                message_type=row["message_type"],
                created_at=row["created_at"],
            )
            for row in result.mappings().all()
        ]

    async def close(
        self, session: AsyncSession, session_id: UUID, user_id: UUID, reason: str
    ) -> SessionResponse:
        """关闭会话并追加关闭消息。"""
        if not reason.strip():
            raise ValueError("关闭会话必须填写原因")
        current = await session.execute(
            select(review_sessions).where(
                review_sessions.c.id == session_id,
                review_sessions.c.user_id == user_id,
            )
        )
        row = current.mappings().first()
        if row is None:
            raise ValueError("审核会话不存在")
        now = datetime.now(UTC)
        await session.execute(
            update(review_sessions)
            .where(review_sessions.c.id == session_id)
            .values(session_status="closed", updated_at=now, state_version=row["state_version"] + 1)
        )
        return self._to_response(row, "会话已关闭")

    @staticmethod
    def _to_response(row: Any, assistant_message: str) -> SessionResponse:
        """将表记录转换为会话响应。"""
        status = str(row["session_status"])
        status_map = {
            "collecting": SessionStatus.OPEN,
            "open": SessionStatus.OPEN,
            "waiting_analysis": SessionStatus.WAITING_ANALYSIS,
            "waiting_human": SessionStatus.WAITING_HUMAN,
            "closed": SessionStatus.CLOSED,
        }
        return SessionResponse(
            session_id=row["id"],
            document_id=row.get("document_id"),
            document_version_id=row["document_version_id"],
            status=status_map.get(status, SessionStatus.OPEN),
            assistant_message=assistant_message,
            created_at=row.get("created_at"),
        )


__all__ = ["SqlSessionRepository"]
