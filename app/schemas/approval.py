"""审批请求和不可变决定记录模型。"""

from datetime import UTC, datetime
from decimal import Decimal
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

    approver_id: UUID | None = None
    decision: DecisionCode
    comment: str = Field(default="", max_length=2000)
    review_comment: str | None = Field(default=None, max_length=2000)
    idempotency_key: str = Field(default="", max_length=128)

    @property
    def resolved_comment(self) -> str:
        """兼容旧 comment 与前端 review_comment 命名。"""
        return self.review_comment if self.review_comment is not None else self.comment


class ApprovalDecisionRecord(BaseModel):
    """不可变审批决定记录。"""

    record_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    approver_id: UUID
    decision: DecisionCode
    comment: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalDecisionResponse(BaseModel):
    """审批决定响应。"""

    task_id: UUID
    document_status: str
    record: ApprovalDecisionRecord


class ApprovalTaskResponse(BaseModel):
    """审批任务列表和详情响应。"""

    task_id: UUID
    document_id: UUID
    document_no: str
    document_type: str
    node_id: UUID
    node_name: str
    node_order: int
    assignee_id: UUID
    assignee_name: str
    task_status: str
    decision: str | None = None
    review_comment: str | None = None
    total_amount: Decimal
    currency: str
    overall_risk_level: str | None = None
    pending_finding_count: int = 0
    applicant_name: str
    applicant_department: str
    created_at: datetime
    processed_at: datetime | None = None


class ApprovalTaskPage(BaseModel):
    """审批任务分页响应。"""

    items: list[ApprovalTaskResponse]
    page: int
    page_size: int
    total: int


class ApprovalHistoryNode(BaseModel):
    """单据审批历史节点。"""

    node_order: int
    node_name: str
    assignee_name: str
    task_status: str
    decision: str | None = None
    review_comment: str | None = None
    processed_at: datetime | None = None


class WorkflowNodeCommand(BaseModel):
    """流程节点配置。"""

    order: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=128)
    approver_role: str = Field(min_length=1, max_length=32)
    approver_names: str = ""
    approver_id: UUID | None = None


class WorkflowCreateCommand(BaseModel):
    """创建审批流程草稿。"""

    name: str = Field(min_length=1, max_length=128)
    document_type: str = Field(default="expense_reimbursement", max_length=32)
    match_condition: str = ""
    nodes: list[WorkflowNodeCommand] = Field(min_length=1)


class WorkflowPatchCommand(BaseModel):
    """更新审批流程草稿。"""

    name: str | None = Field(default=None, max_length=128)
    document_type: str | None = Field(default=None, max_length=32)
    match_condition: str | None = None
    status: str | None = None
    nodes: list[WorkflowNodeCommand] | None = None


class WorkflowNodeResponse(BaseModel):
    """流程节点响应。"""

    node_id: UUID
    order: int
    name: str
    approver_role: str
    approver_names: str
    approver_id: UUID | None = None


class WorkflowTemplateResponse(BaseModel):
    """版本化审批流程响应。"""

    workflow_id: UUID
    name: str
    version: int
    document_type: str
    match_condition: str
    approval_mode: str = "sequential"
    status: str
    nodes: list[WorkflowNodeResponse]
    published_at: datetime | None = None
    updated_at: datetime


class WorkflowPublishCommand(BaseModel):
    """发布流程前填写的审核原因。"""

    reason: str = Field(min_length=1, max_length=500)
