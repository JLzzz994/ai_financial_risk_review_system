"""异步分析任务编排服务。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from app.schemas.analysis import (
    AnalysisEvent,
    AnalysisEventType,
    AnalysisStage,
    AnalysisTaskResponse,
)
from engines.tasks.analysis_tasks import AnalysisTaskResult, run_analysis_task


@dataclass
class _TaskRuntime:
    """任务状态和事件历史的内存实现，生产环境由 PostgreSQL/Redis 持久化。"""

    task: AnalysisTaskResponse
    events: list[AnalysisEvent] = field(default_factory=list)


class AnalysisService:
    """提交分析任务、管理重试并提供 SSE 断点恢复。"""

    def __init__(self) -> None:
        """初始化任务和幂等索引。"""
        self._tasks: dict[UUID, _TaskRuntime] = {}
        self._start_idempotency: dict[tuple[UUID, UUID, str], UUID] = {}
        self._retry_idempotency: dict[tuple[UUID, str], UUID] = {}

    async def start(
        self, document_id: UUID, document_version_id: UUID, idempotency_key: str
    ) -> AnalysisTaskResponse:
        """创建排队任务；相同版本和幂等键始终返回同一任务。"""
        if not idempotency_key.strip():
            raise ValueError("分析任务必须提供幂等键")
        key = (document_id, document_version_id, idempotency_key)
        existing_id = self._start_idempotency.get(key)
        if existing_id is not None:
            return self._tasks[existing_id].task
        task = AnalysisTaskResponse(
            document_id=document_id,
            document_version_id=document_version_id,
        )
        runtime = _TaskRuntime(task)
        self._tasks[task.task_id] = runtime
        self._start_idempotency[key] = task.task_id
        self._append_event(runtime, AnalysisEventType.PROGRESS, "queued", "running")
        return task

    def submit(self, document_version_id: UUID, idempotency_key: str) -> AnalysisTaskResult:
        """兼容旧任务边界；新 API 使用异步 ``start``。"""
        return run_analysis_task(document_version_id, idempotency_key)

    async def retry(self, task_id: UUID, idempotency_key: str) -> AnalysisTaskResponse:
        """失败任务最多自动重试三次，超过上限进入人工接管。"""
        if not idempotency_key.strip():
            raise ValueError("分析重试必须提供幂等键")
        runtime = self._get(task_id)
        cached_id = self._retry_idempotency.get((task_id, idempotency_key))
        if cached_id is not None:
            return self._tasks[cached_id].task
        if runtime.task.stage is not AnalysisStage.FAILED:
            raise ValueError("只有失败任务可以重试")
        if runtime.task.retry_count >= 3:
            runtime.task.stage = AnalysisStage.MANUAL_REVIEW
            runtime.task.manual_takeover = True
            runtime.task.error_message = "自动重试已达上限，需要人工接管"
            self._append_event(runtime, AnalysisEventType.ERROR, "manual_review", "manual_review")
            raise ValueError("分析任务已进入人工接管")
        runtime.task.retry_count += 1
        runtime.task.stage = AnalysisStage.QUEUED
        runtime.task.progress = 0
        runtime.task.error_message = None
        runtime.task.finished_at = None
        self._retry_idempotency[(task_id, idempotency_key)] = task_id
        self._append_event(runtime, AnalysisEventType.PROGRESS, "queued", "retrying")
        return runtime.task

    def mark_failed(self, task_id: UUID, error_message: str) -> AnalysisTaskResponse:
        """由 Celery Worker 写入失败状态和脱敏错误事件。"""
        runtime = self._get(task_id)
        runtime.task.stage = AnalysisStage.FAILED
        runtime.task.error_message = error_message[:500]
        runtime.task.finished_at = datetime.now(UTC)
        self._append_event(runtime, AnalysisEventType.ERROR, "failed", "failed")
        return runtime.task

    def get(self, task_id: UUID) -> AnalysisTaskResponse:
        """查询任务当前事实状态。"""
        return self._get(task_id).task

    def list_events(self, task_id: UUID, last_event_id: int = 0) -> list[AnalysisEvent]:
        """返回指定事件之后的历史，用于 SSE 断线恢复。"""
        if last_event_id < 0:
            raise ValueError("last_event_id 不能小于 0")
        return [event for event in self._get(task_id).events if event.event_id > last_event_id]

    def list_findings(self, task_id: UUID) -> list[dict[str, object]]:
        """返回任务风险项占位；实际结果由风险仓储按版本查询。"""
        self._get(task_id)
        return []

    def _get(self, task_id: UUID) -> _TaskRuntime:
        """获取任务，不存在时返回统一业务错误。"""
        runtime = self._tasks.get(task_id)
        if runtime is None:
            raise ValueError("分析任务不存在")
        return runtime

    @staticmethod
    def _append_event(
        runtime: _TaskRuntime,
        event_type: AnalysisEventType,
        step: str,
        status: str,
    ) -> AnalysisEvent:
        """追加单调递增事件 ID，事件正文不携带附件或敏感输入。"""
        event = AnalysisEvent(
            event_id=len(runtime.events) + 1,
            type=event_type,
            task_id=runtime.task.task_id,
            step=step,
            status=status,
        )
        runtime.events.append(event)
        return event
