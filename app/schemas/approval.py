"""审批请求和不可变决定记录模型。"""

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DecisionCode(StrEnum):
    """审批决定。"""

    APPROVE = "approve"
    RETURN = "return"
    REJECT = "reject"


class ApprovalDecisionCommand(BaseModel):
    """审批人提交决定。"""

    approver_id: UUID
    decision: DecisionCode
    comment: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=1, max_length=128)


class ApprovalDecisionRecord(BaseModel):
    """不可变审批决定记录。"""

    record_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    approver_id: UUID
    decision: DecisionCode
    comment: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalDecisionResponse(BaseModel):
    """审批决定响应。"""

    task_id: UUID
    document_status: str
    record: ApprovalDecisionRecord
