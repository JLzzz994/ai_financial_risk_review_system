"""审核报告草稿与最终固化生命周期测试。"""

import asyncio
from uuid import uuid4

import pytest

from app.schemas.reports import ReportStatus
from app.services.report_service import ReportService


def test_report_can_be_created_as_draft_and_finalized_once() -> None:
    """分析阶段先生成草稿，审批完成后只能固化一次最终报告。"""
    service = ReportService()
    version_id = uuid4()

    draft = service.create_draft(version_id, "待审批风险报告")
    draft_id = draft.report_id
    draft_status = draft.status
    finalized = asyncio.run(service.finalize(version_id, uuid4()))

    assert draft_status is ReportStatus.DRAFT
    assert finalized.report_id == draft_id
    assert finalized.status is ReportStatus.SUCCEEDED

    with pytest.raises(ValueError, match="最终报告已固化"):
        asyncio.run(service.finalize(version_id, uuid4()))


def test_finalization_is_isolated_by_document_version() -> None:
    """不同单据版本各自保留报告，不互相覆盖。"""
    service = ReportService()
    first = service.create_draft(uuid4(), "第一版")
    second = service.create_draft(uuid4(), "第二版")

    assert first.report_id != second.report_id
    assert len(service.reports) == 2
