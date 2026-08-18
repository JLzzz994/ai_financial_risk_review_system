"""审核会话 PostgreSQL 服务。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.sql_session_repository import SqlSessionRepository
from app.schemas.auth import Principal
from app.schemas.sessions import (
    CreateSessionCommand,
    SessionMessageResponse,
    SessionResponse,
)


class PersistentSessionService:
    """持久化会话上下文，Agent 只能通过会话提供辅助结果。"""

    def __init__(self, repository: SqlSessionRepository | None = None) -> None:
        """注入会话仓储。"""
        self.repository = repository or SqlSessionRepository()

    async def create(
        self,
        session: AsyncSession,
        actor: Principal,
        command: CreateSessionCommand,
    ) -> SessionResponse:
        """创建当前用户的审核会话。"""
        async with session.begin():
            version_id = await self.repository.resolve_version(
                session, command.document_id, command.document_version_id
            )
            return await self.repository.create(session, actor.user_id, version_id)

    async def get(
        self, session: AsyncSession, actor: Principal, session_id: UUID
    ) -> SessionResponse:
        """读取当前用户会话。"""
        return await self.repository.get(session, session_id, actor.user_id)

    async def messages(
        self,
        session: AsyncSession,
        actor: Principal,
        session_id: UUID,
        content: str,
        intent: str | None,
    ) -> list[SessionMessageResponse]:
        """追加会话消息并返回历史。"""
        if not content.strip():
            raise ValueError("消息内容不能为空")
        async with session.begin():
            return await self.repository.add_message(
                session, session_id, actor.user_id, content, intent
            )

    async def list_messages(
        self, session: AsyncSession, actor: Principal, session_id: UUID
    ) -> list[SessionMessageResponse]:
        """读取会话消息历史。"""
        return await self.repository.list_messages(session, session_id, actor.user_id)

    async def close(
        self, session: AsyncSession, actor: Principal, session_id: UUID, reason: str
    ) -> SessionResponse:
        """关闭审核会话。"""
        async with session.begin():
            return await self.repository.close(session, session_id, actor.user_id, reason)


__all__ = ["PersistentSessionService"]
