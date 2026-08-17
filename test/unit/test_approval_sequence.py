"""固定顺序审批服务的行为契约测试。"""

import asyncio
from uuid import uuid4

import pytest

from app.schemas.approval import DecisionCode
from app.services.approval_service import ApprovalService


def test_approval_sequence_moves_to_next_node_after_approve() -> None:
    """首节点通过后，单据进入待下一审批节点状态。"""
    service = ApprovalService()
    first_approver, second_approver = uuid4(), uuid4()
    first_task, second_task = service.assign_sequence([first_approver, second_approver])

    result = asyncio.run(
        service.decide(first_task, first_approver, DecisionCode.APPROVE, "首节点同意", "seq-1")
    )

    assert result.task_id == first_task
    assert result.document_status == "pending_approval"
    assert service.statuses[second_task] == "pending"
    assert service.current_task(first_task) == second_task


def test_duplicate_idempotency_key_returns_original_decision() -> None:
    """重复提交相同幂等键只返回原结果，不重复推进审批。"""
    service = ApprovalService()
    task_id = uuid4()
    approver_id = uuid4()
    service.assign(task_id, approver_id)

    first = asyncio.run(
        service.decide(task_id, approver_id, DecisionCode.APPROVE, "同意", "same-key")
    )
    repeated = asyncio.run(
        service.decide(task_id, approver_id, DecisionCode.APPROVE, "重复请求", "same-key")
    )

    assert repeated == first
    assert len(service.records) == 1


def test_return_resets_sequence_to_first_node() -> None:
    """退回决定结束当前审批，并从重新提交后的首节点开始。"""
    service = ApprovalService()
    first_task, second_task = service.assign_sequence([uuid4(), uuid4()])
    first_approver = service.assignees[first_task]
    asyncio.run(service.decide(first_task, first_approver, "approve", "通过", "advance"))
    second_approver = service.assignees[second_task]

    result = asyncio.run(
        service.decide(second_task, second_approver, DecisionCode.RETURN, "补充发票", "return-1")
    )

    assert result.document_status == "returned"
    assert service.resubmit(second_task) == first_task
    assert service.statuses[first_task] == "pending"


def test_non_assigned_approver_cannot_decide() -> None:
    """非当前节点分配人不能提交审批决定。"""
    service = ApprovalService()
    task_id = uuid4()
    service.assign(task_id, uuid4())

    with pytest.raises(PermissionError):
        asyncio.run(service.decide(task_id, uuid4(), DecisionCode.APPROVE, "越权", "forbidden"))
