"""分析任务的 Celery 投递边界。"""

from typing import Any
from uuid import UUID

from app.tasks.celery_app import celery_app


@celery_app.task(  # type: ignore[untyped-decorator]
    name="financial_review.analysis_task",
    bind=True,
    autoretry_for=(RuntimeError,),
    retry_backoff=True,
    max_retries=3,
)
def run_analysis_task(
    self: Any, task_id: str, document_version_id: str, idempotency_key: str
) -> dict[str, str]:
    """Worker 只接收稳定 ID；实际 OCR/RAG/规则编排由后续阶段注入。"""
    del self
    UUID(task_id)
    UUID(document_version_id)
    if not idempotency_key.strip():
        raise ValueError("分析任务必须提供幂等键")
    return {"task_id": task_id, "document_version_id": document_version_id, "status": "queued"}


def enqueue_analysis_task(task_id: UUID, document_version_id: UUID, idempotency_key: str) -> None:
    """向 Celery 投递稳定参数，不在 API 进程执行长任务。"""
    run_analysis_task.delay(str(task_id), str(document_version_id), idempotency_key)


__all__ = ["enqueue_analysis_task", "run_analysis_task"]
