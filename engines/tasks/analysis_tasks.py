"""分析任务边界。"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AnalysisTaskResult:
    """分析任务结果。"""

    document_version_id: UUID
    status: str
    attempts: int


def run_analysis_task(document_version_id: UUID, idempotency_key: str, attempt: int = 1) -> AnalysisTaskResult:
    """校验分析任务参数；Celery 接入前不伪造执行成功。"""
    if not idempotency_key.strip():
        raise ValueError("分析任务必须提供幂等键")
    if attempt > 3:
        return AnalysisTaskResult(document_version_id, "manual_review", attempt)
    raise RuntimeError("Celery 分析任务尚未配置")
