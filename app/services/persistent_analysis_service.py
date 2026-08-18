"""PostgreSQL + Redis 分析任务编排服务。"""

import json
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.sql_analysis_repository import SqlAnalysisTaskRepository
from app.repositories.sql_risk_repository import SqlRiskRepository
from app.schemas.analysis import (
    AnalysisEvent,
    AnalysisEventType,
    AnalysisStage,
    AnalysisTaskResponse,
)


class AnalysisEventStore(Protocol):
    """分析事件存储契约，生产使用 Redis，测试可注入内存实现。"""

    def append(self, task_id: UUID, event: AnalysisEvent) -> None:
        """追加事件。"""

    def list_after(self, task_id: UUID, last_event_id: int) -> list[AnalysisEvent]:
        """返回指定事件之后的历史。"""


class RedisAnalysisEventStore:
    """Redis 列表事件存储，事件正文不包含文件或模型敏感输入。"""

    def __init__(
        self,
        client: object | None = None,
        key_prefix: str = "financial-review:analysis",
    ) -> None:
        """延迟创建 Redis 客户端。"""
        self._client = client
        self._key_prefix = key_prefix

    @property
    def client(self) -> object:
        """获取 Redis 客户端。"""
        if self._client is None:
            from redis import Redis

            self._client = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    def _key(self, task_id: UUID) -> str:
        """拼接事件键。"""
        return f"{self._key_prefix}:events:{task_id}"

    def append(self, task_id: UUID, event: AnalysisEvent) -> None:
        """追加 JSON 事件并保留最近 1000 条。"""
        payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
        self.client.rpush(self._key(task_id), payload)  # type: ignore[attr-defined]
        self.client.ltrim(self._key(task_id), -1000, -1)  # type: ignore[attr-defined]

    def append_atomic(self, task_id: UUID, event: AnalysisEvent) -> AnalysisEvent:
        """使用 Redis INCR 分配跨 Worker 唯一事件 ID 后追加事件。"""
        sequence_key = f"{self._key_prefix}:event-seq:{task_id}"
        event_id = int(self.client.incr(sequence_key))  # type: ignore[attr-defined]
        assigned = event.model_copy(update={"event_id": event_id})
        self.append(task_id, assigned)
        return assigned

    def list_after(self, task_id: UUID, last_event_id: int) -> list[AnalysisEvent]:
        """按事件 ID 过滤 Redis 列表。"""
        values = self.client.lrange(self._key(task_id), 0, -1)  # type: ignore[attr-defined]
        return [
            AnalysisEvent.model_validate(json.loads(value))
            for value in values[last_event_id:]
        ]


class PersistentAnalysisService:
    """持久化任务、Redis 事件和 Celery 投递边界。"""

    def __init__(
        self,
        repository: SqlAnalysisTaskRepository | Any | None = None,
        event_store: AnalysisEventStore | None = None,
    ) -> None:
        """注入仓储和事件存储。"""
        self.repository = repository or SqlAnalysisTaskRepository()
        self.event_store = event_store or RedisAnalysisEventStore()
        self.risk_repository = SqlRiskRepository()

    async def start(
        self,
        session: AsyncSession,
        document_id: UUID,
        document_version_id: UUID,
        idempotency_key: str,
    ) -> AnalysisTaskResponse:
        """创建分析任务并投递 Celery，重复幂等键返回已有任务。"""
        if not idempotency_key.strip():
            raise ValueError("分析任务必须提供幂等键")
        existing = await self.repository.find_by_idempotency(session, idempotency_key)
        if existing is not None:
            return existing
        task = AnalysisTaskResponse(
            document_id=document_id,
            document_version_id=document_version_id,
        )
        async with session.begin():
            await self.repository.create(session, task, idempotency_key, settings.rag_rule_version)
        self._append_event(task, AnalysisEventType.PROGRESS, "queued", "running")
        self._enqueue(task, idempotency_key)
        return task

    async def get(self, session: AsyncSession, task_id: UUID) -> AnalysisTaskResponse:
        """读取任务事实状态。"""
        task = await self.repository.get(session, task_id)
        if task is None:
            raise ValueError("分析任务不存在")
        return task

    async def retry(
        self, session: AsyncSession, task_id: UUID, idempotency_key: str
    ) -> AnalysisTaskResponse:
        """失败任务最多重试三次，超过上限进入人工接管。"""
        if not idempotency_key.strip():
            raise ValueError("分析重试必须提供幂等键")
        task = await self.get(session, task_id)
        if task.stage is not AnalysisStage.FAILED:
            raise ValueError("只有失败任务可以重试")
        if task.retry_count >= 3:
            task.stage = AnalysisStage.MANUAL_REVIEW
            task.manual_takeover = True
            task.error_message = "自动重试已达上限，需要人工接管"
            async with session.begin():
                await self.repository.update(session, task)
            self._append_event(task, AnalysisEventType.ERROR, "manual_review", "manual_review")
            return task
        task.retry_count += 1
        task.stage = AnalysisStage.QUEUED
        task.progress = 0
        task.error_message = None
        task.finished_at = None
        async with session.begin():
            await self.repository.update(session, task)
        self._append_event(task, AnalysisEventType.PROGRESS, "queued", "retrying")
        self._enqueue(task, idempotency_key)
        return task

    async def mark_failed(
        self, session: AsyncSession, task_id: UUID, error_message: str
    ) -> AnalysisTaskResponse:
        """Worker 回写失败状态和脱敏事件。"""
        task = await self.get(session, task_id)
        task.stage = AnalysisStage.FAILED
        task.progress = 100
        task.error_message = error_message[:500]
        task.finished_at = datetime.now(UTC)
        async with session.begin():
            await self.repository.update(session, task)
        self._append_event(task, AnalysisEventType.ERROR, "failed", "failed")
        return task

    def list_events(self, task_id: UUID, last_event_id: int = 0) -> list[AnalysisEvent]:
        """返回 Redis 中指定事件之后的历史。"""
        if last_event_id < 0:
            raise ValueError("last_event_id 不能小于 0")
        return self.event_store.list_after(task_id, last_event_id)

    async def list_findings(
        self, session: AsyncSession, task_id: UUID
    ) -> list[dict[str, object]]:
        """按分析任务绑定的版本查询已落库风险项。"""
        task = await self.repository.get(session, task_id)
        if task is None:
            raise ValueError("分析任务不存在")
        findings = await self.risk_repository.list_by_version(session, task.document_version_id)
        return [
            {
                "rule_code": finding.rule_code,
                "risk_level": finding.level,
                "status": finding.status,
                "message": finding.message,
                "evidence": finding.evidence.model_dump(mode="json")
                if finding.evidence
                else None,
                "suggestion": finding.suggestion,
            }
            for finding in findings
        ]

    def _append_event(
        self, task: AnalysisTaskResponse, event_type: AnalysisEventType, step: str, status: str
    ) -> None:
        """生成单调事件 ID 并写入事件存储。"""
        events = self.event_store.list_after(task.task_id, 0)
        event = AnalysisEvent(
            event_id=len(events) + 1,
            type=event_type,
            task_id=task.task_id,
            step=step,
            status=status,
        )
        self.event_store.append(task.task_id, event)

    @staticmethod
    def _enqueue(task: AnalysisTaskResponse, idempotency_key: str) -> None:
        """只向 Celery 传递稳定 ID 和幂等键，不传文件内容。"""
        try:
            from app.tasks.analysis_tasks import enqueue_analysis_task

            enqueue_analysis_task(task.task_id, task.document_version_id, idempotency_key)
        except Exception as exc:
            raise RuntimeError("分析任务队列不可用") from exc


__all__ = ["PersistentAnalysisService", "RedisAnalysisEventStore"]
