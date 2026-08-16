"""版本化审核报告服务。"""

from uuid import UUID

from app.schemas.reports import ReportListItem, ReportStatus, ReviewReport


class ReportService:
    """报告只追加不覆盖。"""

    def __init__(self) -> None:
        """初始化报告存储。"""
        self.reports: list[ReviewReport] = []

    def finalize_report(self, document_version_id: UUID, content: str) -> ReviewReport:
        """为指定单据版本创建报告。"""
        if not content.strip():
            raise ValueError("报告内容不能为空")
        report = ReviewReport(document_version_id=document_version_id, status=ReportStatus.SUCCEEDED, content=content)
        self.reports.append(report)
        return report

    def list_reports(self, document_version_id: UUID) -> list[ReportListItem]:
        """返回指定单据版本的报告列表摘要。"""
        return [ReportListItem(report_id=r.report_id, document_version_id=r.document_version_id, status=r.status, created_at=r.created_at) for r in self.reports if r.document_version_id == document_version_id]

    def get_report(self, report_id: UUID) -> ReviewReport:
        """按报告 ID 返回指定版本详情。"""
        for report in self.reports:
            if report.report_id == report_id:
                return report
        raise ValueError("报告不存在")
