"""审核报告的 PostgreSQL 仓储。"""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import DocumentVersion, FinancialDocument, ReviewReport
from app.schemas.reports import ReportListItem, ReportStatus
from app.schemas.reports import ReviewReport as ReviewReportSchema


class SqlReportRepository:
    """追加报告草稿、固化最终报告并按版本查询。"""

    async def create_draft(
        self,
        session: AsyncSession,
        document_version_id: UUID,
        content: str | dict[str, Any],
        generated_by: str | None = None,
    ) -> ReviewReportSchema:
        """创建不可覆盖的报告草稿。"""
        context = await session.execute(
            select(
                DocumentVersion.document_id,
                DocumentVersion.version_no,
                FinancialDocument.document_no,
            )
            .join(FinancialDocument, DocumentVersion.document_id == FinancialDocument.id)
            .where(DocumentVersion.id == document_version_id)
        )
        row = context.first()
        if row is None:
            raise ValueError("单据版本不存在")
        report_id = uuid4()
        payload = content if isinstance(content, dict) else {"summary": content}
        report = ReviewReport(
            id=report_id,
            document_id=row[0],
            document_version_id=document_version_id,
            report_status="draft",
            report_content=payload,
            report_markdown=(
                content
                if isinstance(content, str)
                else json.dumps(content, ensure_ascii=False)
            ),
            generated_by=generated_by,
            report_version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(report)
        await session.flush()
        return self._to_schema(report, row[1])

    async def finalize(
        self, session: AsyncSession, document_version_id: UUID, actor: UUID
    ) -> ReviewReportSchema:
        """锁定最新草稿并固化为最终报告，历史报告不覆盖。"""
        existing = await session.scalar(
            select(ReviewReport)
            .where(
                ReviewReport.document_version_id == document_version_id,
                ReviewReport.report_status == "succeeded",
            )
            .limit(1)
        )
        if existing is not None:
            raise ValueError("最终报告已固化")
        draft = await session.scalar(
            select(ReviewReport)
            .where(
                ReviewReport.document_version_id == document_version_id,
                ReviewReport.report_status == "draft",
            )
            .order_by(ReviewReport.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        if draft is None:
            raise ValueError("报告草稿不存在")
        draft.report_status = "succeeded"
        draft.finalized_by = actor
        draft.finalized_at = datetime.now(UTC)
        draft.updated_at = datetime.now(UTC)
        await session.flush()
        version_no = await session.scalar(
            select(DocumentVersion.version_no).where(DocumentVersion.id == document_version_id)
        )
        return self._to_schema(draft, int(version_no or 1))

    async def get_by_id(
        self, session: AsyncSession, report_id: UUID
    ) -> ReviewReportSchema | None:
        """按报告 ID 查询详情。"""
        result = await session.execute(
            select(ReviewReport, DocumentVersion.version_no)
            .join(DocumentVersion, ReviewReport.document_version_id == DocumentVersion.id)
            .where(ReviewReport.id == report_id)
        )
        row = result.first()
        return self._to_schema(row[0], row[1]) if row is not None else None

    async def get_latest_by_version(
        self, session: AsyncSession, document_version_id: UUID
    ) -> ReviewReportSchema | None:
        """按版本查询最新报告。"""
        result = await session.execute(
            select(ReviewReport, DocumentVersion.version_no)
            .join(DocumentVersion, ReviewReport.document_version_id == DocumentVersion.id)
            .where(ReviewReport.document_version_id == document_version_id)
            .order_by(ReviewReport.created_at.desc())
            .limit(1)
        )
        row = result.first()
        return self._to_schema(row[0], row[1]) if row is not None else None

    async def list_by_document(
        self, session: AsyncSession, document_id: UUID
    ) -> list[ReportListItem]:
        """列出单据所有版本报告摘要。"""
        result = await session.execute(
            select(ReviewReport, DocumentVersion.version_no)
            .join(DocumentVersion, ReviewReport.document_version_id == DocumentVersion.id)
            .where(ReviewReport.document_id == document_id)
            .order_by(ReviewReport.created_at.desc())
        )
        return [
            ReportListItem(
                report_id=row[0].id,
                document_version_id=row[0].document_version_id,
                status=ReportStatus(row[0].report_status),
                report_status=ReportStatus(row[0].report_status),
                overall_risk_level=row[0].overall_risk_level,
                created_at=row[0].created_at,
            )
            for row in result.all()
        ]

    async def list_by_version(
        self, session: AsyncSession, document_version_id: UUID
    ) -> list[ReportListItem]:
        """列出指定版本的报告摘要。"""
        result = await session.execute(
            select(ReviewReport)
            .where(ReviewReport.document_version_id == document_version_id)
            .order_by(ReviewReport.created_at.desc())
        )
        return [
            ReportListItem(
                report_id=report.id,
                document_version_id=report.document_version_id,
                status=ReportStatus(report.report_status),
                report_status=ReportStatus(report.report_status),
                overall_risk_level=report.overall_risk_level,
                created_at=report.created_at,
            )
            for report in result.scalars().all()
        ]

    @staticmethod
    def _to_schema(report: ReviewReport, version_no: int) -> ReviewReportSchema:
        """将 ORM 报告转换为 API 模型。"""
        status = ReportStatus(report.report_status)
        content: str | dict[str, Any]
        if report.report_content:
            content = report.report_content
        else:
            content = report.report_markdown or ""
        return ReviewReportSchema(
            report_id=report.id,
            document_id=report.document_id,
            document_version_id=report.document_version_id,
            version_no=version_no,
            status=status,
            report_status=status,
            overall_risk_level=report.overall_risk_level,
            rule_version="",
            content=content,
            generated_at=report.generated_at,
            created_at=report.created_at,
        )


__all__ = ["SqlReportRepository"]
