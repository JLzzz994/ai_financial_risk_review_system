"""审核报告查询、固化和异步导出 API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.dependencies.auth import get_current_principal
from app.schemas.reports import (
    ExportTaskResponse,
    ReportExportCommand,
    ReportListItem,
    ReviewReport,
)
from app.services.persistent_report_service import PersistentReportService
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/v1", tags=["reports"])
service = ReportService()
persistent_service = PersistentReportService()


@router.get("/document-versions/{document_version_id}/reports", response_model=list[ReportListItem])
async def list_reports(
    document_version_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[ReportListItem]:
    """查询指定单据版本的报告列表。"""
    if settings.document_backend == "postgres":
        await get_current_principal(authorization, session)
        return await persistent_service.repository.list_by_version(session, document_version_id)
    return service.list_reports(document_version_id)


@router.get("/documents/{document_id}/review-reports", response_model=list[ReportListItem])
async def list_document_reports(
    document_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[ReportListItem]:
    """查询单据各版本报告摘要。"""
    if settings.document_backend != "postgres":
        return []
    await get_current_principal(authorization, session)
    return await persistent_service.list_by_document(session, document_id)


@router.get("/reports/{report_id}", response_model=ReviewReport)
async def get_report(
    report_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> ReviewReport:
    """按报告 ID 查询完整详情。"""
    try:
        if settings.document_backend == "postgres":
            await get_current_principal(authorization, session)
            return await persistent_service.get_by_id(session, report_id)
        return service.get_report(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/review-reports/{document_version_id}", response_model=ReviewReport)
async def get_latest_report(
    document_version_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> ReviewReport:
    """按文档版本查询最新报告，作为前端主链路接口。"""
    try:
        if settings.document_backend == "postgres":
            await get_current_principal(authorization, session)
            return await persistent_service.get(session, document_version_id)
        report = next(
            (
                item
                for item in reversed(service.reports)
                if item.document_version_id == document_version_id
            ),
            None,
        )
        if report is None:
            raise ValueError("报告不存在")
        return report
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/review-reports/{document_version_id}/finalize", response_model=ReviewReport)
async def finalize_report(
    document_version_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> ReviewReport:
    """由人工审批人员固化报告最终状态。"""
    try:
        if settings.document_backend == "postgres":
            principal = await get_current_principal(authorization, session)
            return await persistent_service.finalize(
                session, document_version_id, principal.user_id
            )
        return await service.finalize(document_version_id, UUID(int=0))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/review-reports/{document_version_id}/export", response_model=ExportTaskResponse)
async def start_report_export(
    document_version_id: UUID,
    body: ReportExportCommand,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> ExportTaskResponse:
    """创建 PDF/XLSX 异步导出任务。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=503, detail="报告导出持久化未启用")
    await get_current_principal(authorization, session)
    try:
        return await persistent_service.start_export(
            session,
            document_version_id,
            body.format,
            idempotency_key or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/review-reports/exports/{export_task_id}", response_model=ExportTaskResponse)
async def get_export_task(export_task_id: UUID) -> ExportTaskResponse:
    """查询异步导出状态。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=404, detail="导出任务不存在")
    try:
        return persistent_service.get_export(export_task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/review-reports/exports/{export_task_id}/download")
async def download_export(export_task_id: UUID) -> Response:
    """下载已完成的报告导出快照。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=404, detail="导出任务不存在")
    try:
        task = persistent_service.get_export(export_task_id)
        content = persistent_service.get_export_content(export_task_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{task.file_name or "report"}"'},
    )
