"""审批状态机测试。"""

from engines.approval.state_machine import ApprovalDecision, next_document_status


def test_sequential_status_transition() -> None:
    """非末节点通过后仍等待下一审批节点。"""
    assert next_document_status(ApprovalDecision.APPROVE, False) == "pending_approval"
    assert next_document_status(ApprovalDecision.APPROVE, True) == "approved"
    assert next_document_status(ApprovalDecision.RETURN, True) == "returned"
