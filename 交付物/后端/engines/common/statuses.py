"""数据库持久化状态的单一来源，所有值使用小写英文。"""

from enum import StrEnum


class DocumentStatus(StrEnum):
    """财务单据生命周期状态。"""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    REVIEWING = "reviewing"
    PENDING_APPROVAL = "pending_approval"
    RETURNED = "returned"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    VOIDED = "voided"


class ApprovalTaskStatus(StrEnum):
    """审批任务状态。"""

    PENDING = "pending"
    APPROVED = "approved"
    RETURNED = "returned"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalDecision(StrEnum):
    """审批人员可以提交的最终决定。"""

    APPROVE = "approve"
    RETURN = "return"
    REJECT = "reject"


class ReviewReportStatus(StrEnum):
    """审核报告生成状态。"""

    DRAFT = "draft"
    GENERATING = "generating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
