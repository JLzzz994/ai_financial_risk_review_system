"""顺序审批状态机。"""

from enum import StrEnum


class ApprovalDecision(StrEnum):
    """审批人员允许提交的决定。"""

    APPROVE = "approve"
    RETURN = "return"
    REJECT = "reject"


def next_document_status(decision: ApprovalDecision, is_last_node: bool) -> str:
    """根据当前节点决定下一个单据状态。"""
    if decision is ApprovalDecision.RETURN:
        return "returned"
    if decision is ApprovalDecision.REJECT:
        return "rejected"
    return "approved" if is_last_node else "pending_approval"
