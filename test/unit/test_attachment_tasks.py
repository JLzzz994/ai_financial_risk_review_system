"""解析任务契约测试。"""

from uuid import uuid4

import pytest

from app.tasks.attachment_tasks import parse_attachment_task


def test_task_requires_idempotency_key() -> None:
    """解析任务必须使用稳定幂等键。"""
    with pytest.raises(ValueError):
        parse_attachment_task(uuid4(), "")


def test_task_enters_manual_review_after_retry_limit() -> None:
    """超过三次尝试后进入人工接管。"""
    result = parse_attachment_task(uuid4(), "key-1", attempt=4)
    assert result.status == "manual_review"
