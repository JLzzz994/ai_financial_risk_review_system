"""附件解析任务的 Celery Worker 入口。"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from redis.exceptions import ConnectionError as RedisConnectionError

from app.config import settings
from app.db.engine import async_session_factory
from app.repositories.sql_attachment_repository import SqlAttachmentRepository
from app.tasks.celery_app import celery_app
from app.tasks.safety import sanitize_error
from engines.ocr.contracts import OcrAdapter, OcrRequest, OcrResult

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
    page_count: int | None = None
    confidence: float | None = None
    recognized_text: str | None = None
    idempotency_key: str = ""


class AttachmentStatePort(Protocol):
    """附件事实状态回写端口，生产实现应更新附件表。"""

    def save(self, state: AttachmentParseState) -> None:
        """保存 parsing/failed/manual_review 状态。"""

    def get_request(self, attachment_id: UUID, document_version_id: UUID) -> OcrRequest:
        """读取附件对象键，组装 OCR 请求。"""


class SqlAttachmentStatePort:
    """生产附件事实状态端口，回写 PostgreSQL 附件元数据。"""

    def save(self, state: AttachmentParseState) -> None:
        asyncio.run(self._save(state))

    def get_request(self, attachment_id: UUID, document_version_id: UUID) -> OcrRequest:
        """从 PostgreSQL 获取对象键，禁止 Worker 自行拼接物理路径。"""
        return asyncio.run(self._get_request(attachment_id, document_version_id))

    async def _get_request(self, attachment_id: UUID, document_version_id: UUID) -> OcrRequest:
        """查询附件版本并转换为 OCR 窄契约。"""
        repository = SqlAttachmentRepository()
        async with async_session_factory() as session:
            record = await repository.get(session, attachment_id)
            if record is None or record.document_version_id != document_version_id:
                raise ValueError("附件版本不存在")
            return OcrRequest(attachment_id, record.object_key)

    async def _save(self, state: AttachmentParseState) -> None:
        repository = SqlAttachmentRepository()
        async with async_session_factory() as session:
            record = await repository.get(session, state.attachment_id)
            if record is None or record.document_version_id != state.document_version_id:
                raise ValueError("附件版本不存在")
            record.parse_status = state.status
            record.parse_error = state.error_message
            record.retry_count = state.retry_count
            record.parse_idempotency_key = state.idempotency_key
            await session.rollback()
            async with session.begin():
                await repository.save(session, record)
                if state.status == "succeeded" and state.recognized_text is not None:
                    from app.repositories.sql_attachment_repository import ParseResultRecord

                    await repository.append_parse_result(
                        session,
                        ParseResultRecord(
                            result_id=uuid4(),
                            attachment_id=state.attachment_id,
                            document_version_id=state.document_version_id,
                            document_category="unknown",
                            full_text=state.recognized_text,
                            fields={},
                            evidence_positions={"page_count": state.page_count or 0},
                            confidence=state.confidence,
                            provider_name="paddleocr",
                            provider_version="3.x",
                            created_at=datetime.now(UTC),
                            idempotency_key=state.idempotency_key,
                        ),
                    )


_attachment_state_port: AttachmentStatePort | None = SqlAttachmentStatePort()
_ocr_adapter: OcrAdapter | None = None


def set_attachment_state_port(port: AttachmentStatePort | None) -> None:
    """注入附件状态事实仓储；未注入时任务明确失败。"""
    global _attachment_state_port
    _attachment_state_port = port


def set_attachment_ocr_adapter(adapter: OcrAdapter | None) -> None:
    """注入 OCR 适配器；生产启动组装时注册 PaddleOCR，测试注入 Fake。"""
    global _ocr_adapter
    _ocr_adapter = adapter


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
        idempotency_key=idempotency_key,
    )


def _get_ocr_adapter() -> OcrAdapter:
    """从应用 ProviderRegistry 获取默认 PaddleOCR，避免任务直接依赖 SDK。"""
    if _ocr_adapter is not None:
        return _ocr_adapter
    from app.providers import build_provider_registry
    from engines.common.minio_storage import MinioFileStorage

    storage = MinioFileStorage.from_settings(
        settings.minio_endpoint,
        settings.minio_access_key,
        settings.minio_secret_key,
        settings.minio_bucket,
        settings.minio_secure,
    )
    return cast(OcrAdapter, build_provider_registry(storage).get("ocr", "paddleocr"))


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
    port = _attachment_state_port
    if port is None:
        raise RuntimeError("附件状态仓储尚未配置")
    idempotency_digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:32]
    key = (
        "financial-review:attachment-parse:"
        f"{attachment_uuid}:{version_uuid}:{idempotency_digest}"
    )
    client: Any | None = None
    cached: str | None = None
    try:
        client = _redis_client()
        cached = client.get(key)
    except Exception as exc:
        logger.warning(
            "attachment_parse_cache_read_failed",
            extra={
                "task_id": attachment_id,
                "document_version_id": document_version_id,
                "request_id": idempotency_key,
                "error": sanitize_error(str(exc)),
            },
        )
    if cached:
        try:
            cached_payload = cast(dict[str, str], json.loads(cached))
        except Exception as exc:
            logger.warning(
                "attachment_parse_cache_corrupted",
                extra={
                    "task_id": attachment_id,
                    "document_version_id": document_version_id,
                    "request_id": idempotency_key,
                    "error": sanitize_error(str(exc)),
                },
            )
            cached = None
            cached_payload = {}
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
        request = port.get_request(attachment_uuid, version_uuid)
        result = asyncio.run(_ocr_adapter_result(_get_ocr_adapter(), request))
        succeeded = AttachmentParseState(
            attachment_uuid,
            version_uuid,
            "succeeded",
            attempt,
            None,
            result.page_count,
            result.confidence,
            result.text,
            idempotency_key,
        )
        port.save(succeeded)
        payload = {
            "attachment_id": attachment_id,
            "status": "succeeded",
            "page_count": str(result.page_count),
            "confidence": str(result.confidence),
        }
        _cache_set_nonfatal(
            client, key, payload, attachment_id, document_version_id, idempotency_key
        )
        logger.info(
            "attachment_parse_succeeded",
            extra={
                "task_id": attachment_id,
                "document_version_id": document_version_id,
                "request_id": idempotency_key,
                "page_count": result.page_count,
                "confidence": result.confidence,
                "provider": "paddleocr",
            },
        )
        return payload
    except Exception as exc:
        failed = attachment_parse_state(
            attachment_uuid,
            version_uuid,
            idempotency_key,
            attempt=attempt,
            error=str(exc),
        )
        port.save(failed)
        logger.error(
            (
                "attachment_parse_manual_review"
                if failed.status == "manual_review"
                else "attachment_parse_state"
            ),
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
        _cache_set_nonfatal(
            client, key, payload, attachment_id, document_version_id, idempotency_key
        )
        if attempt < 3:
            raise self.retry(exc=exc, countdown=2**attempt) from exc
        return payload


def _cache_set_nonfatal(
    client: Any | None,
    key: str,
    payload: dict[str, str],
    attachment_id: str,
    document_version_id: str,
    request_id: str,
) -> None:
    """写入 Redis 短缓存；失败不得影响 PostgreSQL 事实状态和任务结果。"""
    if client is None:
        return
    try:
        client.set(key, json.dumps(payload, ensure_ascii=False), ex=86400)
    except Exception as exc:
        logger.warning(
            "attachment_parse_cache_write_failed",
            extra={
                "task_id": attachment_id,
                "document_version_id": document_version_id,
                "request_id": request_id,
                "error": sanitize_error(str(exc)),
            },
        )


async def _ocr_adapter_result(adapter: OcrAdapter, request: OcrRequest) -> OcrResult:
    """执行 OCR 协议调用，保持 Worker 与 SDK 解耦。"""
    return await adapter.recognize(request)


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
    "set_attachment_ocr_adapter",
]
