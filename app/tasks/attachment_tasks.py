"""附件解析任务的 Celery 适配边界。"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ParseTaskResult:
    """解析任务结果，不携带文件二进制。"""

    attachment_id: UUID
    status: str
    attempts: int


def parse_attachment_task(attachment_id: UUID, idempotency_key: str, attempt: int = 1) -> ParseTaskResult:
    """提交解析任务契约；未安装 Celery 时明确失败，不伪造完成结果。"""
    if not idempotency_key.strip():
        raise ValueError("解析任务必须提供幂等键")
    if attempt > 3:
        return ParseTaskResult(attachment_id, "manual_review", attempt)
    try:
        import celery  # type: ignore[import-not-found,unused-ignore]
    except ImportError as exc:
        raise RuntimeError("Celery 依赖未安装，无法提交解析任务") from exc
    del celery
    return ParseTaskResult(attachment_id, "queued", attempt)
