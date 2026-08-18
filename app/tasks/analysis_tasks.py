"""分析任务的 Celery 投递边界和 Worker 阶段编排。"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from app.db.engine import async_session_factory
from app.repositories.sql_analysis_repository import SqlAnalysisTaskRepository
from app.schemas.analysis import AnalysisEvent, AnalysisEventType, AnalysisStage
from app.services.persistent_analysis_service import RedisAnalysisEventStore
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnalysisWorkerState:
    """Worker 内部的最小状态，不携带文件内容或 ORM 对象。"""

    task_id: UUID
    document_version_id: UUID
    stage: AnalysisStage = AnalysisStage.QUEUED
    retry_count: int = 0
    manual_takeover: bool = False
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class StageAdvanceResult:
    """状态变更及对应 SSE 事件。"""

    state: AnalysisWorkerState
    events: tuple[AnalysisEvent, ...] = ()


class AnalysisStateStore(Protocol):
    """Worker 状态回写端口，测试可注入内存实现。"""

    async def save(self, state: AnalysisWorkerState) -> None:
        """保存当前阶段。"""


class AnalysisEventPublisher(Protocol):
    """Worker 阶段事件发布端口，生产实现写 Redis。"""

    async def publish(self, event: AnalysisEvent) -> None:
        """发布一个可断点重放事件。"""


_STAGE_ORDER = {
    AnalysisStage.QUEUED: 0,
    AnalysisStage.PARSING: 1,
    AnalysisStage.EXTRACTING: 2,
    AnalysisStage.ANALYZING: 3,
    AnalysisStage.AGGREGATING: 4,
    AnalysisStage.SUCCEEDED: 5,
}


def advance_analysis_stage(
    state: AnalysisWorkerState,
    stage: AnalysisStage,
    *,
    error: str | None = None,
) -> StageAdvanceResult:
    """按固定顺序推进阶段；失败重试耗尽时进入人工接管。"""
    if stage is AnalysisStage.FAILED:
        if state.retry_count >= 3:
            next_stage = AnalysisStage.MANUAL_REVIEW
            next_state = replace(
                state,
                stage=next_stage,
                manual_takeover=True,
                error_message=_safe_error(error),
            )
        else:
            next_stage = AnalysisStage.FAILED
            next_state = replace(state, stage=next_stage, error_message=_safe_error(error))
    elif stage is AnalysisStage.MANUAL_REVIEW:
        next_stage = stage
        next_state = replace(
            state,
            stage=stage,
            manual_takeover=True,
            error_message=_safe_error(error),
        )
    else:
        current_rank = _STAGE_ORDER.get(state.stage, -1)
        requested_rank = _STAGE_ORDER.get(stage, -1)
        if requested_rank < current_rank:
            raise ValueError("分析阶段不能回退")
        next_stage = stage
        next_state = replace(state, stage=stage)
    event_type = AnalysisEventType.RESULT if next_stage is AnalysisStage.SUCCEEDED else (
        AnalysisEventType.ERROR if next_stage in {AnalysisStage.FAILED, AnalysisStage.MANUAL_REVIEW}
        else AnalysisEventType.PROGRESS
    )
    event = AnalysisEvent(
        event_id=1,
        type=event_type,
        task_id=state.task_id,
        step=next_stage.value,
        status=next_stage.value,
        data={"document_version_id": str(state.document_version_id)},
    )
    return StageAdvanceResult(next_state, (event,))


def _safe_error(message: str | None) -> str | None:
    """只保留脱敏后的短错误，不记录外部输入和附件原文。"""
    return message[:500] if message else None


async def _run_analysis_pipeline_with_ports(
    state: AnalysisWorkerState,
    state_store: AnalysisStateStore,
    event_publisher: AnalysisEventPublisher,
    stage_runner: Callable[[AnalysisStage], Awaitable[None]],
) -> AnalysisWorkerState:
    """执行固定顺序流水线，适配器失败时只返回失败或人工接管。"""
    next_event_id = 1
    for stage in (
        AnalysisStage.PARSING,
        AnalysisStage.EXTRACTING,
        AnalysisStage.ANALYZING,
        AnalysisStage.AGGREGATING,
        AnalysisStage.SUCCEEDED,
    ):
        try:
            await stage_runner(stage)
        except Exception as exc:
            failed = advance_analysis_stage(
                state, AnalysisStage.FAILED, error=f"阶段 {stage.value} 失败：{exc}"
            ).state
            await state_store.save(failed)
            await event_publisher.publish(
                AnalysisEvent(
                    event_id=next_event_id,
                    type=AnalysisEventType.ERROR,
                    task_id=failed.task_id,
                    step=failed.stage.value,
                    status=failed.stage.value,
                    data={"document_version_id": str(failed.document_version_id)},
                )
            )
            return failed
        result = advance_analysis_stage(state, stage)
        state = result.state
        await state_store.save(state)
        for event in result.events:
            await event_publisher.publish(event.model_copy(update={"event_id": next_event_id}))
            next_event_id += 1
    return state


async def run_analysis_pipeline(
    task: AnalysisWorkerState,
    stage_runner: Callable[[AnalysisStage], Awaitable[None]],
    progress_sink: Callable[[AnalysisEvent], Awaitable[None]],
) -> AnalysisWorkerState:
    """运行可测试的阶段流水线；进度输出由调用方注入。"""

    class _NoopStateStore:
        async def save(self, _state: AnalysisWorkerState) -> None:
            return None

    class _SinkPublisher:
        async def publish(self, event: AnalysisEvent) -> None:
            await progress_sink(event)

    return await _run_analysis_pipeline_with_ports(
        task, _NoopStateStore(), _SinkPublisher(), stage_runner
    )


async def _persist_analysis_state(state: AnalysisWorkerState) -> None:
    """使用本次任务独立会话回写 PostgreSQL 并追加 Redis 事件。"""
    repository = SqlAnalysisTaskRepository()
    event_store = RedisAnalysisEventStore()
    async with async_session_factory() as session:
        task = await repository.get(session, state.task_id)
        if task is None:
            raise ValueError("分析任务不存在")
        # 查询会开启隐式事务；更新前显式结束它，保证每次回写边界清晰。
        await session.rollback()
        task.stage = state.stage
        task.retry_count = state.retry_count
        task.error_message = state.error_message
        task.manual_takeover = state.manual_takeover
        task.finished_at = datetime.now(UTC) if state.stage in {
            AnalysisStage.FAILED,
            AnalysisStage.MANUAL_REVIEW,
            AnalysisStage.SUCCEEDED,
        } else None
        async with session.begin():
            await repository.update(session, task)
        event = AnalysisEvent(
            event_id=len(event_store.list_after(state.task_id, 0)) + 1,
            type=AnalysisEventType.RESULT if state.stage is AnalysisStage.SUCCEEDED else (
                AnalysisEventType.ERROR
                if state.stage in {AnalysisStage.FAILED, AnalysisStage.MANUAL_REVIEW}
                else AnalysisEventType.PROGRESS
            ),
            task_id=state.task_id,
            step=state.stage.value,
            status=state.stage.value,
            data={"document_version_id": str(state.document_version_id)},
        )
        event_store.append(state.task_id, event)


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
    task_uuid = UUID(task_id)
    version_uuid = UUID(document_version_id)
    if not idempotency_key.strip():
        raise ValueError("分析任务必须提供幂等键")
    try:
        return asyncio.run(_run_analysis(task_uuid, version_uuid, self.request.retries))
    except RuntimeError as exc:
        # 外部适配器不可用时持久化失败并交给 Celery 做有界重试。
        state = AnalysisWorkerState(task_uuid, version_uuid, retry_count=self.request.retries + 1)
        if self.request.retries >= 3:
            state = advance_analysis_stage(state, AnalysisStage.FAILED, error=str(exc)).state
            asyncio.run(_persist_analysis_state(state))
            return {
                "task_id": task_id,
                "document_version_id": document_version_id,
                "status": state.stage.value,
            }
        failed = advance_analysis_stage(state, AnalysisStage.FAILED, error=str(exc)).state
        asyncio.run(_persist_analysis_state(failed))
        raise self.retry(exc=exc, countdown=2**self.request.retries) from exc


async def _run_analysis(task_id: UUID, document_version_id: UUID, retries: int) -> dict[str, str]:
    """执行固定阶段门禁；模型适配器未接入时不得伪造成功。"""
    state = AnalysisWorkerState(task_id, document_version_id, retry_count=retries)

    class _DatabaseStateStore:
        async def save(self, value: AnalysisWorkerState) -> None:
            await _persist_analysis_state(value)

    class _RedisPublisher:
        async def publish(self, event: AnalysisEvent) -> None:
            del event

    async def _unconfigured_stage(stage: AnalysisStage) -> None:
        raise RuntimeError(f"分析适配器尚未配置（{stage.value}），任务进入重试或人工接管")

    result = await _run_analysis_pipeline_with_ports(
        state, _DatabaseStateStore(), _RedisPublisher(), _unconfigured_stage
    )
    if result.stage in {AnalysisStage.FAILED, AnalysisStage.MANUAL_REVIEW}:
        raise RuntimeError(result.error_message or "分析任务失败")
    return {
        "task_id": str(task_id),
        "document_version_id": str(document_version_id),
        "status": result.stage.value,
    }


def enqueue_analysis_task(task_id: UUID, document_version_id: UUID, idempotency_key: str) -> None:
    """向 Celery 投递稳定参数，不在 API 进程执行长任务。"""
    run_analysis_task.delay(str(task_id), str(document_version_id), idempotency_key)


__all__ = ["enqueue_analysis_task", "run_analysis_task"]
