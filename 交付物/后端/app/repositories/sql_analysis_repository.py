"""PostgreSQL 分析任务仓储。"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extended import analysis_tasks
from app.schemas.analysis import AnalysisStage, AnalysisTaskResponse


class SqlAnalysisTaskRepository:
    """持久化分析任务状态和幂等索引。"""

    async def find_by_idempotency(
        self, session: AsyncSession, idempotency_key: str
    ) -> AnalysisTaskResponse | None:
        """按全局幂等键查询已有任务。"""
        result = await session.execute(
            select(analysis_tasks).where(analysis_tasks.c.idempotency_key == idempotency_key)
        )
        row = result.mappings().first()
        return self._to_response(row) if row is not None else None

    async def get(self, session: AsyncSession, task_id: UUID) -> AnalysisTaskResponse | None:
        """按任务 ID查询最新状态。"""
        result = await session.execute(select(analysis_tasks).where(analysis_tasks.c.id == task_id))
        row = result.mappings().first()
        return self._to_response(row) if row is not None else None

    async def create(
        self,
        session: AsyncSession,
        task: AnalysisTaskResponse,
        idempotency_key: str,
        rule_version: str,
    ) -> AnalysisTaskResponse:
        """插入排队任务，任务不携带文件或 ORM 对象。"""
        await session.execute(
            insert(analysis_tasks).values(
                id=task.task_id,
                document_id=task.document_id,
                document_version_id=task.document_version_id,
                task_status="queued",
                current_step=task.stage.value,
                rule_version=rule_version,
                model_metadata_json={},
                retry_count=task.retry_count,
                idempotency_key=idempotency_key,
                started_at=task.started_at,
            )
        )
        return task

    async def update(
        self,
        session: AsyncSession,
        task: AnalysisTaskResponse,
    ) -> AnalysisTaskResponse:
        """更新阶段、重试次数和脱敏错误，不覆盖任务主键。"""
        await session.execute(
            update(analysis_tasks)
            .where(analysis_tasks.c.id == task.task_id)
            .values(
                task_status=task.stage.value,
                current_step=task.stage.value,
                retry_count=task.retry_count,
                error_message=task.error_message,
                finished_at=task.finished_at,
            )
        )
        return task

    async def update_worker_state(
        self, session: AsyncSession, task: AnalysisTaskResponse
    ) -> AnalysisTaskResponse:
        """Worker 状态回写，保护已完成或人工接管的终态不被覆盖。"""
        result = await session.execute(
            update(analysis_tasks)
            .where(
                analysis_tasks.c.id == task.task_id,
                analysis_tasks.c.task_status.notin_(["succeeded", "manual_review"]),
            )
            .values(
                task_status=task.stage.value,
                current_step=task.stage.value,
                retry_count=task.retry_count,
                error_message=task.error_message,
                finished_at=task.finished_at,
            )
        )
        if int(getattr(result, "rowcount", 0)) == 0:
            current = await self.get(session, task.task_id)
            if current is None:
                raise ValueError("分析任务不存在")
            if current.stage.value != task.stage.value:
                raise RuntimeError("分析任务已被其他 Worker 推进")
        return task

    @staticmethod
    def _to_response(row: Any) -> AnalysisTaskResponse:
        """将数据表状态映射到 API 任务契约。"""
        raw_stage = str(row.get("current_step") or row.get("task_status") or "queued")
        try:
            stage = AnalysisStage(raw_stage)
        except ValueError:
            stage = AnalysisStage.QUEUED
        return AnalysisTaskResponse(
            task_id=UUID(str(row["id"])),
            document_id=UUID(str(row["document_id"])),
            document_version_id=UUID(str(row["document_version_id"])),
            stage=stage,
            progress=_progress_for(stage),
            retry_count=int(row.get("retry_count") or 0),
            error_message=row.get("error_message"),
            manual_takeover=stage is AnalysisStage.MANUAL_REVIEW,
            started_at=row.get("started_at") or datetime.now(UTC),
            finished_at=row.get("finished_at"),
        )


def _progress_for(stage: AnalysisStage) -> int:
    """统一阶段进度，前端只展示离散安全进度。"""
    return {
        AnalysisStage.QUEUED: 0,
        AnalysisStage.PARSING: 25,
        AnalysisStage.EXTRACTING: 45,
        AnalysisStage.ANALYZING: 70,
        AnalysisStage.AGGREGATING: 90,
        AnalysisStage.SUCCEEDED: 100,
        AnalysisStage.FAILED: 100,
        AnalysisStage.MANUAL_REVIEW: 100,
    }[stage]


__all__ = ["SqlAnalysisTaskRepository"]
