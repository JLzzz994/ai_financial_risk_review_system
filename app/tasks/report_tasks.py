"""审核报告导出 Celery 任务。"""

import json
from typing import Any
from uuid import UUID

from app.config import settings
from app.tasks.celery_app import celery_app


def _redis_client() -> Any:
    """创建 Worker 侧 Redis 客户端。"""
    from redis import Redis

    return Redis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="financial_review.report_export",
    bind=True,
    autoretry_for=(RuntimeError,),
    retry_backoff=True,
    max_retries=3,
)
def run_report_export(
    self: Any, export_task_id: str, document_version_id: str, export_format: str
) -> dict[str, str]:
    """Worker 更新导出状态；不接收附件二进制和 ORM 对象。"""
    del self
    UUID(export_task_id)
    UUID(document_version_id)
    if export_format not in {"pdf", "xlsx"}:
        raise ValueError("导出格式不合法")
    client = _redis_client()
    key = f"financial-review:report-export:{export_task_id}"
    raw = client.get(key)
    if raw is None:
        raise ValueError("导出任务不存在")
    payload = json.loads(raw)
    payload["status"] = "succeeded"
    client.set(key, json.dumps(payload, ensure_ascii=False), ex=86400)
    return {"export_task_id": export_task_id, "status": "succeeded"}


def enqueue_report_export(
    export_task_id: UUID, document_version_id: UUID, export_format: str
) -> None:
    """投递报告导出任务。"""
    run_report_export.delay(str(export_task_id), str(document_version_id), export_format)


__all__ = ["enqueue_report_export", "run_report_export"]
