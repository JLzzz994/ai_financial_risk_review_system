"""异步分析任务编排与 SSE 事件重放测试。"""

import asyncio
from uuid import uuid4

import pytest

from app.services.analysis_service import AnalysisService


def test_start_is_idempotent_and_records_progress_event() -> None:
    """相同单据版本和幂等键只创建一个排队任务。"""
    service = AnalysisService()
    document_id, version_id = uuid4(), uuid4()

    first = asyncio.run(service.start(document_id, version_id, "analysis-key"))
    repeated = asyncio.run(service.start(document_id, version_id, "analysis-key"))

    assert repeated.task_id == first.task_id
    assert first.stage == "queued"
    assert service.list_events(first.task_id, last_event_id=0)[0].type == "progress"


def test_retry_after_failure_increments_count_and_replays_events() -> None:
    """失败任务重试增加次数，超过三次进入人工接管。"""
    service = AnalysisService()
    task = asyncio.run(service.start(uuid4(), uuid4(), "retry-key"))
    service.mark_failed(task.task_id, "OCR 服务超时")

    retried = asyncio.run(service.retry(task.task_id, "retry-1"))
    assert retried.retry_count == 1
    assert retried.stage == "queued"

    service.mark_failed(task.task_id, "再次超时")
    asyncio.run(service.retry(task.task_id, "retry-2"))
    service.mark_failed(task.task_id, "第三次超时")
    asyncio.run(service.retry(task.task_id, "retry-3"))
    service.mark_failed(task.task_id, "超过上限")
    with pytest.raises(ValueError, match="人工接管"):
        asyncio.run(service.retry(task.task_id, "retry-4"))

    events = service.list_events(task.task_id, last_event_id=1)
    assert any(event.type == "error" for event in events)
