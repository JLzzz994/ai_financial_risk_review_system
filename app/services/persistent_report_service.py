"""版本化审核报告和异步导出服务。"""

import base64
import json
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.sql_report_repository import SqlReportRepository
from app.schemas.reports import (
    ExportTaskResponse,
    ReportListItem,
    ReviewReport,
)


class ReportExportStore(Protocol):
    """报告导出状态存储契约。"""

    def get(self, key: str) -> str | None:
        """读取导出状态。"""

    def set(self, key: str, value: str, ex: int) -> object:
        """保存导出状态。"""


class RedisReportExportStore:
    """使用 Redis 保存短期导出任务状态和脱敏报告快照。"""

    def __init__(self, client: object | None = None) -> None:
        """延迟创建 Redis 客户端。"""
        self._client = client

    @property
    def client(self) -> object:
        """获取 Redis 客户端。"""
        if self._client is None:
            from redis import Redis

            self._client = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    def get(self, key: str) -> str | None:
        """读取任务。"""
        return self.client.get(key)  # type: ignore[attr-defined,no-any-return]

    def set(self, key: str, value: str, ex: int) -> object:
        """写入任务并设置过期时间。"""
        return self.client.set(key, value, ex=ex)  # type: ignore[attr-defined]


class PersistentReportService:
    """将报告事实写入 PostgreSQL，导出状态放入 Redis。"""

    def __init__(
        self,
        repository: SqlReportRepository | None = None,
        export_store: ReportExportStore | None = None,
    ) -> None:
        """注入报告仓储和导出状态存储。"""
        self.repository = repository or SqlReportRepository()
        self.export_store = export_store or RedisReportExportStore()

    async def create_draft(
        self,
        session: AsyncSession,
        document_version_id: UUID,
        content: str | dict[str, object],
        generated_by: str | None = None,
    ) -> ReviewReport:
        """创建报告草稿。"""
        async with session.begin():
            return await self.repository.create_draft(
                session, document_version_id, content, generated_by
            )

    async def finalize(
        self, session: AsyncSession, document_version_id: UUID, actor: UUID
    ) -> ReviewReport:
        """最终通过或驳回后固化报告，历史版本不覆盖。"""
        async with session.begin():
            return await self.repository.finalize(session, document_version_id, actor)

    async def get(
        self, session: AsyncSession, document_version_id: UUID
    ) -> ReviewReport:
        """读取指定版本最新报告。"""
        report = await self.repository.get_latest_by_version(session, document_version_id)
        if report is None:
            raise ValueError("报告不存在")
        return report

    async def get_by_id(self, session: AsyncSession, report_id: UUID) -> ReviewReport:
        """按报告 ID 读取报告。"""
        report = await self.repository.get_by_id(session, report_id)
        if report is None:
            raise ValueError("报告不存在")
        return report

    async def list_by_document(
        self, session: AsyncSession, document_id: UUID
    ) -> list[ReportListItem]:
        """列出单据报告摘要。"""
        return await self.repository.list_by_document(session, document_id)

    async def start_export(
        self,
        session: AsyncSession,
        document_version_id: UUID,
        export_format: str,
        idempotency_key: str,
    ) -> ExportTaskResponse:
        """创建异步导出任务，只向 Celery 传递 ID 和格式。"""
        if export_format not in {"pdf", "xlsx"}:
            raise ValueError("导出格式必须为 pdf 或 xlsx")
        if not idempotency_key.strip():
            raise ValueError("导出任务必须提供幂等键")
        report = await self.get(session, document_version_id)
        key = f"financial-review:report-export:idempotency:{idempotency_key}"
        cached = self.export_store.get(key)
        if cached:
            return ExportTaskResponse.model_validate_json(cached)
        task = ExportTaskResponse(
            export_task_id=uuid4(),
            status="running",
            file_name=f"审核报告_{document_version_id}.{export_format}",
        )
        payload = {
            **task.model_dump(mode="json"),
            "document_version_id": str(document_version_id),
            "content": report.content,
            "format": export_format,
        }
        self.export_store.set(key, json.dumps(payload, ensure_ascii=False), ex=86400)
        self.export_store.set(
            f"financial-review:report-export:{task.export_task_id}",
            json.dumps(payload, ensure_ascii=False),
            ex=86400,
        )
        self._enqueue(task.export_task_id, document_version_id, export_format)
        return task

    def get_export(self, export_task_id: UUID) -> ExportTaskResponse:
        """读取导出任务状态。"""
        raw = self.export_store.get(f"financial-review:report-export:{export_task_id}")
        if not raw:
            raise ValueError("导出任务不存在")
        return ExportTaskResponse.model_validate(json.loads(raw))

    def get_export_content(self, export_task_id: UUID) -> bytes:
        """读取已完成导出的脱敏报告快照。"""
        raw = self.export_store.get(f"financial-review:report-export:{export_task_id}")
        if not raw:
            raise ValueError("导出任务不存在")
        payload = json.loads(raw)
        if payload.get("status") != "succeeded":
            raise ValueError("导出任务尚未完成")
        snapshot = payload.get("snapshot_b64")
        if isinstance(snapshot, str):
            return base64.b64decode(snapshot)
        return json.dumps(payload.get("content", {}), ensure_ascii=False, indent=2).encode("utf-8")

    @staticmethod
    def _enqueue(export_task_id: UUID, document_version_id: UUID, export_format: str) -> None:
        """向 Celery 投递稳定参数，API 不执行导出。"""
        try:
            from app.tasks.report_tasks import enqueue_report_export

            enqueue_report_export(export_task_id, document_version_id, export_format)
        except Exception as exc:
            raise RuntimeError("报告导出队列不可用") from exc


__all__ = ["PersistentReportService", "RedisReportExportStore", "ReportExportStore"]
