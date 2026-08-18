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
    client = _redis_client()
    key = f"financial-review:report-export:{export_task_id}"
    raw = client.get(key)
    if raw is None:
        raise ValueError("导出任务不存在")
    try:
        payload = json.loads(raw)
    except Exception as exc:
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
    except (ConnectionError, OSError, RuntimeError, ValueError) as exc:
        payload["status"] = "manual_review" if self.request.retries >= 3 else "failed"
        payload["error_message"] = sanitize_error(str(exc))
        client.set(
            key,
            json.dumps(payload, ensure_ascii=False),
            ex=settings.report_export_ttl_seconds,
        )
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
    client.set(key, json.dumps(payload, ensure_ascii=False), ex=settings.report_export_ttl_seconds)
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
