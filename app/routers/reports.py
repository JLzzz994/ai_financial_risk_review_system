"""审核报告 API。"""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.schemas.reports import ReportListItem, ReviewReport
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/v1", tags=["reports"])
service = ReportService()


@router.get("/document-versions/{document_version_id}/reports", response_model=list[ReportListItem])
async def list_reports(document_version_id: UUID) -> list[ReportListItem]:
    """查询指定单据版本的报告列表。"""
    return service.list_reports(document_version_id)


@router.get("/reports/{report_id}", response_model=ReviewReport)
async def get_report(report_id: UUID) -> ReviewReport:
    """查询单个报告完整详情，列表接口只返回摘要。"""
    try:
        return service.get_report(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
