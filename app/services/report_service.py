"""版本化审核报告服务。"""

from uuid import UUID

from app.schemas.reports import ReportListItem, ReportStatus, ReviewReport


class ReportService:
    """报告只追加不覆盖。"""

    def __init__(self) -> None:
        """初始化报告存储。"""
        self.reports: list[ReviewReport] = []

    def create_draft(self, document_version_id: UUID, content: str) -> ReviewReport:
        """为分析阶段创建可追踪的报告草稿。"""
        if not content.strip():
            raise ValueError("报告内容不能为空")
        draft = ReviewReport(
            document_version_id=document_version_id,
            status=ReportStatus.DRAFT,
            content=content,
        )
        self.reports.append(draft)
        return draft

    async def finalize(self, document_version_id: UUID, actor: UUID) -> ReviewReport:
        """将指定版本的唯一草稿固化为最终报告。"""
        del actor  # 最终审批人由上层权限服务校验，此处只固化报告版本。
        return self._finalize(document_version_id)

    def _finalize(self, document_version_id: UUID) -> ReviewReport:
        """同步执行报告固化，供异步入口和兼容入口共用。"""
        version_reports = [
            report for report in self.reports if report.document_version_id == document_version_id
        ]
        if any(report.status is ReportStatus.SUCCEEDED for report in version_reports):
            raise ValueError("最终报告已固化")
        draft = next(
            (report for report in reversed(version_reports) if report.status is ReportStatus.DRAFT),
            None,
        )
        if draft is None:
            raise ValueError("报告草稿不存在")
        draft.status = ReportStatus.SUCCEEDED
        return draft

    def finalize_report(self, document_version_id: UUID, content: str) -> ReviewReport:
        """为指定单据版本创建报告。"""
        self.create_draft(document_version_id, content)
        return self._finalize(document_version_id)

    def list_reports(self, document_version_id: UUID) -> list[ReportListItem]:
        """返回指定单据版本的报告列表摘要。"""
        return [
            ReportListItem(
                report_id=r.report_id,
                document_version_id=r.document_version_id,
                status=r.status,
                created_at=r.created_at,
            )
            for r in self.reports
            if r.document_version_id == document_version_id
        ]

    def get_report(self, report_id: UUID) -> ReviewReport:
        """按报告 ID 返回指定版本详情。"""
        for report in self.reports:
            if report.report_id == report_id:
                return report
        raise ValueError("报告不存在")
