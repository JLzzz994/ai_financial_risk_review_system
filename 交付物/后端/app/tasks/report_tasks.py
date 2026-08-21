"""审核报告导出 Celery 任务。"""

import base64
import json
import logging
from typing import Any, Protocol
from uuid import UUID

from redis.exceptions import ConnectionError as RedisConnectionError

from app.config import settings
from app.tasks.celery_app import celery_app
from app.tasks.safety import sanitize_error

logger = logging.getLogger(__name__)


class ReportExporter(Protocol):
    """报告格式导出器；实际 PDF/XLSX 实现由应用注入。"""

    def export(self, content: object, export_format: str) -> bytes:
        """生成导出内容。"""


_report_exporter: ReportExporter | None = None


def set_report_exporter(exporter: ReportExporter | None) -> None:
    """设置 Worker 使用的导出器，未设置时保持失败而不伪造成功。"""
    global _report_exporter
    _report_exporter = exporter


def _redis_client() -> Any:
    """创建 Worker 侧 Redis 客户端。"""
    from redis import Redis

    try:
        return Redis.from_url(settings.redis_url, decode_responses=True)
    except Exception as exc:
        raise RuntimeError(sanitize_error(f"Redis 连接失败：{exc}")) from exc


def _final_report_failure(
    export_task_id: str,
    document_version_id: str,
    request_id: str,
    error: str,
    client: Any | None = None,
    key: str | None = None,
) -> dict[str, str]:
    """尽力保存报告终态；Redis 不可用时仍记录最终失败。"""
    message = sanitize_error(error)
    payload = {
        "export_task_id": export_task_id,
        "status": "manual_review",
        "error_message": message,
    }
    if client is not None and key is not None:
        try:
            client.set(
                key,
                json.dumps(payload, ensure_ascii=False),
                ex=settings.report_export_ttl_seconds,
            )
        except Exception as exc:
            logger.error(
                "report_export_final_state_unavailable",
                extra={
                    "task_id": export_task_id,
                    "document_version_id": document_version_id,
                    "request_id": request_id,
                    "error": sanitize_error(str(exc)),
                },
            )
    logger.error(
        "report_export_manual_review",
        extra={
            "task_id": export_task_id,
            "document_version_id": document_version_id,
            "request_id": request_id,
            "status": "manual_review",
        },
    )
    return payload


def _write_report_state(client: Any, key: str, payload: dict[str, Any]) -> None:
    """统一写入报告状态，Redis 异常转换为可重试错误。"""
    try:
        client.set(
            key,
            json.dumps(payload, ensure_ascii=False),
            ex=settings.report_export_ttl_seconds,
        )
    except Exception as exc:
        raise RuntimeError(sanitize_error(f"报告状态写入失败：{exc}")) from exc


@celery_app.task(  # type: ignore[untyped-decorator]
    name="financial_review.report_export",
    bind=True,
    autoretry_for=(RuntimeError, ConnectionError, RedisConnectionError, OSError),
    retry_backoff=True,
    max_retries=3,
)
def run_report_export(
    self: Any,
    export_task_id: str,
    document_version_id: str,
    export_format: str,
    request_id: str | None = None,
) -> dict[str, str]:
    """Worker 更新导出状态；不接收附件二进制和 ORM 对象。"""
    UUID(export_task_id)
    UUID(document_version_id)
    if export_format not in {"pdf", "xlsx"}:
        raise ValueError("导出格式不合法")
    key = f"financial-review:report-export:{export_task_id}"
    request_key = request_id or export_task_id
    try:
        client = _redis_client()
        raw = client.get(key)
        if raw is None:
            raise ValueError("导出任务不存在")
    except Exception as exc:
        if self.request.retries >= 3:
            return _final_report_failure(
                export_task_id, document_version_id, request_key, str(exc),
            )
        raise RuntimeError(sanitize_error(str(exc))) from exc
    try:
        payload = json.loads(raw)
    except Exception as exc:
        if self.request.retries >= 3:
            return _final_report_failure(
                export_task_id, document_version_id, request_key, str(exc), client, key
            )
        raise RuntimeError(sanitize_error(f"报告导出状态损坏：{exc}")) from exc
    if payload.get("status") in {"succeeded", "manual_review"}:
        return {"export_task_id": export_task_id, "status": payload["status"]}
    try:
        if _report_exporter is None:
            raise RuntimeError("报告导出适配器尚未配置")
        generated = _report_exporter.export(payload.get("content", {}), export_format)
        if not generated:
            raise RuntimeError("报告导出器未返回内容")
        payload["status"] = "succeeded"
        payload["snapshot_b64"] = base64.b64encode(generated).decode("ascii")
    except Exception as exc:
        payload["status"] = "manual_review" if self.request.retries >= 3 else "failed"
        payload["error_message"] = sanitize_error(str(exc))
        try:
            _write_report_state(client, key, payload)
        except RuntimeError as write_exc:
            if self.request.retries >= 3:
                return _final_report_failure(
                    export_task_id, document_version_id, request_key,
                    str(write_exc), client, key,
                )
            raise self.retry(exc=write_exc, countdown=2**self.request.retries) from write_exc
        logger.warning(
            "report_export_failure",
            extra={
                "task_id": export_task_id,
                "document_version_id": document_version_id,
                "request_id": request_id or export_task_id,
            },
        )
        if self.request.retries < 3:
            raise self.retry(exc=exc, countdown=2**self.request.retries) from exc
        return {"export_task_id": export_task_id, "status": payload["status"]}
    try:
        _write_report_state(client, key, payload)
    except RuntimeError as write_exc:
        if self.request.retries >= 3:
            return _final_report_failure(
                export_task_id, document_version_id, request_key,
                str(write_exc), client, key,
            )
        raise self.retry(exc=write_exc, countdown=2**self.request.retries) from write_exc
    logger.info(
        "report_export_succeeded",
        extra={
            "task_id": export_task_id,
            "document_version_id": document_version_id,
            "request_id": request_id or export_task_id,
            "status": "succeeded",
        },
    )
    return {"export_task_id": export_task_id, "status": "succeeded"}


def enqueue_report_export(
    export_task_id: UUID,
    document_version_id: UUID,
    export_format: str,
    request_id: str | None = None,
) -> None:
    """投递报告导出任务。"""
    run_report_export.delay(
        str(export_task_id),
        str(document_version_id),
        export_format,
        request_id or str(export_task_id),
    )


__all__ = ["ReportExporter", "enqueue_report_export", "run_report_export", "set_report_exporter"]
