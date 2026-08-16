"""OCR、模型和分析任务契约测试。"""

from uuid import uuid4

import pytest

from engines.tasks.analysis_tasks import run_analysis_task


def test_analysis_requires_idempotency_and_manual_handoff() -> None:
    """验证幂等键和三次失败后的人工接管。"""
    with pytest.raises(ValueError):
        run_analysis_task(uuid4(), "")
    result = run_analysis_task(uuid4(), "analysis-1", attempt=4)
    assert result.status == "manual_review"
