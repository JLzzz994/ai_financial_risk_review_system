"""异步分析任务查询、重试和 SSE 事件接口。"""

import json
from collections.abc import Iterator
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.analysis import AnalysisTaskResponse, StartAnalysisCommand
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/api/v1", tags=["analysis"])
service = AnalysisService()


@router.post(
    "/documents/{document_id}/analysis",
    response_model=AnalysisTaskResponse,
    status_code=202,
)
async def start_analysis(
    document_id: UUID,
    command: StartAnalysisCommand,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> AnalysisTaskResponse:
    """创建分析任务并立即返回排队状态，不在 API 进程执行长任务。"""
    try:
        return await service.start(document_id, command.document_version_id, idempotency_key or "")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/analysis-tasks/{task_id}", response_model=AnalysisTaskResponse)
async def get_analysis_task(task_id: UUID) -> AnalysisTaskResponse:
    """查询任务事实状态，供刷新页面和 SSE 断线恢复使用。"""
    try:
        return service.get(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/analysis-tasks/{task_id}/retry", response_model=AnalysisTaskResponse)
async def retry_analysis_task(
    task_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> AnalysisTaskResponse:
    """重试失败分析任务，超过上限时转人工接管。"""
    try:
        return await service.retry(task_id, idempotency_key or "")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/analysis-tasks/{task_id}/findings")
async def list_analysis_findings(task_id: UUID) -> list[dict[str, object]]:
    """查询任务已落库风险项。"""
    try:
        return service.list_findings(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/analysis-tasks/{task_id}/events")
async def stream_analysis_events(
    task_id: UUID, last_event_id: int = 0
) -> StreamingResponse:
    """以 SSE 返回事件历史，支持通过 last_event_id 断点续传。"""
    try:
        events = service.list_events(task_id, last_event_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    def event_stream() -> Iterator[str]:
        """序列化有限事件历史；后续 Worker 事件通过 Redis Pub/Sub 接入。"""
        for event in events:
            payload = json.dumps(
                event.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            yield f"id: {event.event_id}\ndata: {payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
