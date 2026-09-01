"""慧经营对账异步分析流水线边界。

真正的 Celery task 只需要调用本模块定义的阶段；未配置 Worker 时绝不伪造成功。
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ReconciliationStage(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    NORMALIZING = "normalizing"
    RULE_EVALUATING = "rule_evaluating"
    POLICY_RETRIEVING = "policy_retrieving"
    EXPLAINING = "explaining"
    AGGREGATING = "aggregating"
    SUCCEEDED = "succeeded"
    MANUAL_REVIEW = "manual_review"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ReconciliationTaskPlan:
    document_version_id: UUID
    idempotency_key: str
    stages: tuple[ReconciliationStage, ...]


def build_reconciliation_task_plan(
    document_version_id: UUID,
    idempotency_key: str,
) -> ReconciliationTaskPlan:
    """生成稳定、可重放的 Celery 工作流阶段。"""
    if not idempotency_key.strip():
        raise ValueError("对账分析必须提供幂等键")
    return ReconciliationTaskPlan(
        document_version_id=document_version_id,
        idempotency_key=idempotency_key,
        stages=(
            ReconciliationStage.PARSING,
            ReconciliationStage.NORMALIZING,
            ReconciliationStage.RULE_EVALUATING,
            ReconciliationStage.POLICY_RETRIEVING,
            ReconciliationStage.EXPLAINING,
            ReconciliationStage.AGGREGATING,
        ),
    )


def run_reconciliation_task(
    document_version_id: UUID,
    idempotency_key: str,
    attempt: int = 1,
) -> ReconciliationTaskPlan:
    """生产 Worker 接入前明确失败；超过三次则由上层转人工。"""
    plan = build_reconciliation_task_plan(document_version_id, idempotency_key)
    if attempt > 3:
        return ReconciliationTaskPlan(
            document_version_id=plan.document_version_id,
            idempotency_key=plan.idempotency_key,
            stages=(ReconciliationStage.MANUAL_REVIEW,),
        )
    raise RuntimeError("Celery 对账分析 Worker 尚未配置")


__all__ = [
    "ReconciliationStage",
    "ReconciliationTaskPlan",
    "build_reconciliation_task_plan",
    "run_reconciliation_task",
]
