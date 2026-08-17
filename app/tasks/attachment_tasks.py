"""附件解析任务的 Celery 适配边界。"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ParseTaskResult:
    """解析任务结果，不携带文件二进制。"""

    attachment_id: UUID
    status: str
    attempts: int
    document_version_id: UUID | None = None
    current_step: str = "queued"
    error_code: str | None = None


def parse_attachment_task(
    attachment_id: UUID,
    idempotency_key: str,
    attempt: int = 1,
    document_version_id: UUID | None = None,
) -> ParseTaskResult:
    """提交解析任务契约；未安装 Celery 时明确失败，不伪造完成结果。"""
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
    try:
        import celery  # type: ignore[import-not-found,unused-ignore]
    except ImportError as exc:
        raise RuntimeError("Celery 依赖未安装，无法提交解析任务") from exc
    del celery
    return ParseTaskResult(
        attachment_id,
        "queued",
        attempt,
        document_version_id,
        current_step="queued",
    )
