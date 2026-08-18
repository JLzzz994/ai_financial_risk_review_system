"""审核会话 API。"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.dependencies.auth import get_current_principal
from app.schemas.sessions import (
    CloseSessionCommand,
    CreateSessionCommand,
    SessionMessage,
    SessionMessageResponse,
    SessionResponse,
)
from app.services.persistent_session_service import PersistentSessionService
from app.services.session_service import SessionService

router = APIRouter(prefix="/api/v1/review-sessions", tags=["review-sessions"])
service = SessionService()
persistent_service = PersistentSessionService()


@router.post("", response_model=SessionResponse)
async def create_session(
    command: CreateSessionCommand | None = Body(default=None),
    document_version_id: UUID | None = None,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    """创建绑定单据版本的审核会话。"""
    resolved = command or CreateSessionCommand(document_version_id=document_version_id)
    try:
        if settings.document_backend == "postgres":
            principal = await get_current_principal(authorization, session)
            return await persistent_service.create(session, principal, resolved)
        version_id = resolved.document_version_id
        if version_id is None:
            raise ValueError("会话必须绑定 document_version_id")
        return service.create(version_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session_detail(
    session_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    """查询审核会话状态。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=404, detail="审核会话不存在")
    try:
        principal = await get_current_principal(authorization, session)
        return await persistent_service.get(session, principal, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{session_id}/messages", response_model=list[SessionMessageResponse])
async def send_message(
    session_id: UUID,
    message: SessionMessage,
    document_version_id: UUID | None = None,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[SessionMessageResponse]:
    """发送审核消息并返回持久化消息历史。"""
    try:
        if settings.document_backend == "postgres":
            principal = await get_current_principal(authorization, session)
            return await persistent_service.messages(
                session, principal, session_id, message.content, message.intent
            )
        if document_version_id is None:
            raise ValueError("memory 模式需要 document_version_id")
        response = service.handle_message(session_id, document_version_id, message)
        return [
            SessionMessageResponse(
                message_id=UUID(int=0),
                role="assistant",
                content=response.assistant_message,
                message_type="assistant_hint",
                created_at=response.created_at or datetime.now(UTC),
            )
        ]
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{session_id}/messages", response_model=list[SessionMessageResponse])
async def list_messages(
    session_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[SessionMessageResponse]:
    """查询审核会话消息历史。"""
    if settings.document_backend != "postgres":
        return []
    try:
        principal = await get_current_principal(authorization, session)
        return await persistent_service.list_messages(session, principal, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{session_id}/close", response_model=SessionResponse)
async def close_session(
    session_id: UUID,
    command: CloseSessionCommand,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    """关闭审核会话。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=404, detail="审核会话不存在")
    try:
        principal = await get_current_principal(authorization, session)
        return await persistent_service.close(session, principal, session_id, command.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
