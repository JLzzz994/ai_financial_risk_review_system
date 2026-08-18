"""附件解析任务的 Celery Worker 入口。"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID

from redis.exceptions import ConnectionError as RedisConnectionError

from app.config import settings
from app.db.engine import async_session_factory
from app.repositories.sql_attachment_repository import SqlAttachmentRepository
from app.tasks.celery_app import celery_app
from app.tasks.safety import sanitize_error

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParseTaskResult:
    """解析任务结果，不携带文件二进制。"""

    attachment_id: UUID
    status: str
    attempts: int
    document_version_id: UUID | None = None
    current_step: str = "queued"
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class AttachmentParseState:
    """解析任务状态，不携带附件内容。"""

    attachment_id: UUID
    document_version_id: UUID
    status: str = "queued"
    retry_count: int = 0
    error_message: str | None = None


class AttachmentStatePort(Protocol):
    """附件事实状态回写端口，生产实现应更新附件表。"""

    def save(self, state: AttachmentParseState) -> None:
        """保存 parsing/failed/manual_review 状态。"""


class SqlAttachmentStatePort:
    """生产附件事实状态端口，回写 PostgreSQL 附件元数据。"""

    def save(self, state: AttachmentParseState) -> None:
        asyncio.run(self._save(state))

    async def _save(self, state: AttachmentParseState) -> None:
        repository = SqlAttachmentRepository()
        async with async_session_factory() as session:
            record = await repository.get(session, state.attachment_id)
            if record is None or record.document_version_id != state.document_version_id:
                raise ValueError("附件版本不存在")
            record.parse_status = state.status
            record.parse_error = state.error_message
            await session.rollback()
            async with session.begin():
                await repository.save(session, record)


_attachment_state_port: AttachmentStatePort | None = SqlAttachmentStatePort()


def set_attachment_state_port(port: AttachmentStatePort | None) -> None:
    """注入附件状态事实仓储；未注入时任务明确失败。"""
    global _attachment_state_port
    _attachment_state_port = port


def attachment_parse_state(
    attachment_id: UUID,
    document_version_id: UUID,
    idempotency_key: str,
    *,
    attempt: int = 0,
    error: str | None = None,
) -> AttachmentParseState:
    """校验稳定参数并计算有界重试后的状态。"""
    if not idempotency_key.strip():
        raise ValueError("解析任务必须提供幂等键")
    if attempt < 0:
        raise ValueError("解析尝试次数不能小于 0")
    status = "manual_review" if attempt >= 3 else ("failed" if error else "queued")
    return AttachmentParseState(
        attachment_id,
        document_version_id,
        status,
        min(attempt, 3),
        sanitize_error(error) if error else None,
    )


def _redis_client() -> Any:
    """创建 Worker 侧短期状态客户端。"""
    from redis import Redis

    try:
        return Redis.from_url(settings.redis_url, decode_responses=True)
    except Exception as exc:
        raise RuntimeError(sanitize_error(f"Redis 连接失败：{exc}")) from exc


@celery_app.task(  # type: ignore[untyped-decorator]
    name="financial_review.attachment_parse",
    bind=True,
    max_retries=3,
    autoretry_for=(RuntimeError, ConnectionError, RedisConnectionError, OSError),
    retry_backoff=True,
)
def run_attachment_parse(
    self: Any,
    attachment_id: str,
    document_version_id: str,
    idempotency_key: str,
) -> dict[str, str]:
    """Worker 只接收附件/版本 ID，未配置解析器时失败而非伪造成功。"""
    attachment_uuid = UUID(attachment_id)
    version_uuid = UUID(document_version_id)
    attempt = int(self.request.retries)
    key = f"financial-review:attachment-parse:{attachment_uuid}"
    client = _redis_client()
    port = _attachment_state_port
    if port is None:
        raise RuntimeError("附件状态仓储尚未配置")
    cached = client.get(key)
    if cached:
        try:
            cached_payload = cast(dict[str, str], json.loads(cached))
        except Exception as exc:
            failed = attachment_parse_state(
                attachment_uuid, version_uuid, idempotency_key,
                attempt=attempt, error=sanitize_error(str(exc)),
            )
            port.save(failed)
            if attempt < 3:
                raise self.retry(
                    exc=RuntimeError(failed.error_message), countdown=2**attempt
                ) from exc
            return {
                "attachment_id": attachment_id,
                "status": "manual_review",
                "error_message": failed.error_message or "",
            }
        if cached_payload.get("status") in {"succeeded", "manual_review"}:
            logger.info(
                "attachment_parse_terminal",
                extra={
                    "task_id": attachment_id,
                    "document_version_id": document_version_id,
                    "request_id": idempotency_key,
                    "status": cached_payload["status"],
                },
            )
            return cached_payload
    try:
        raise RuntimeError("OCR 解析适配器尚未配置")
    except Exception as exc:
        failed = attachment_parse_state(
            attachment_uuid,
            version_uuid,
            idempotency_key,
            attempt=attempt,
            error=str(exc),
        )
        port.save(failed)
        logger.warning(
            "attachment_parse_state",
            extra={
                "task_id": attachment_id,
                "document_version_id": document_version_id,
                "request_id": idempotency_key,
                "status": failed.status,
            },
        )
        payload = {
            "attachment_id": attachment_id,
            "status": failed.status,
            "error_message": failed.error_message or "",
        }
        client.set(key, json.dumps(payload, ensure_ascii=False), ex=86400)
        if attempt < 3:
            raise self.retry(exc=exc, countdown=2**attempt) from exc
        return payload


def parse_attachment_task(
    attachment_id: UUID,
    idempotency_key: str,
    attempt: int = 1,
    document_version_id: UUID | None = None,
) -> ParseTaskResult:
    """仅投递解析任务；API 进程不直接执行 OCR。"""
    if not idempotency_key.strip():
        raise ValueError("解析任务必须提供幂等键")
    if attempt < 1:
        raise ValueError("解析尝试次数必须从 1 开始")
    if attempt > 3:
        return ParseTaskResult(
            attachment_id,
            "manual_review",
            attempt,
            document_version_id,
            current_step="manual_review",
            error_code="parse_retry_exhausted",
        )
    run_attachment_parse.delay(
        str(attachment_id),
        str(document_version_id or UUID(int=0)),
        idempotency_key,
    )
    return ParseTaskResult(
        attachment_id,
        "queued",
        attempt,
        document_version_id,
        current_step="queued",
    )


__all__ = [
    "AttachmentParseState",
    "AttachmentStatePort",
    "SqlAttachmentStatePort",
    "ParseTaskResult",
    "attachment_parse_state",
    "parse_attachment_task",
    "run_attachment_parse",
    "set_attachment_state_port",
]
