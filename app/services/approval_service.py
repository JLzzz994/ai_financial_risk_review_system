"""审批服务，最终决定只能由分配审批人提交。"""

from uuid import UUID

from app.schemas.approval import ApprovalDecisionCommand, ApprovalDecisionRecord, ApprovalDecisionResponse
from engines.approval.state_machine import ApprovalDecision, next_document_status


class ApprovalService:
    """固定顺序审批服务。"""

    def __init__(self) -> None:
        """初始化任务和幂等记录。"""
        self.assignees: dict[UUID, UUID] = {}
        self.statuses: dict[UUID, str] = {}
        self.records: list[ApprovalDecisionRecord] = []
        self.idempotency: set[tuple[UUID, str]] = set()

    def assign(self, task_id: UUID, approver_id: UUID, is_last_node: bool = True) -> None:
        """分配顺序审批节点。"""
        self.assignees[task_id] = approver_id
        self.statuses[task_id] = "pending"
        del is_last_node

    def submit_decision(self, task_id: UUID, command: ApprovalDecisionCommand, is_last_node: bool = True) -> ApprovalDecisionResponse:
        """校验审批人、幂等键和任务状态后保存不可变决定。"""
        if self.assignees.get(task_id) != command.approver_id:
            raise PermissionError("只有分配的审批人可以提交决定")
        if (task_id, command.idempotency_key) in self.idempotency:
            raise ValueError("重复的幂等请求")
        if self.statuses.get(task_id) != "pending":
            raise ValueError("审批任务状态不允许提交决定")
        self.idempotency.add((task_id, command.idempotency_key))
        status = next_document_status(ApprovalDecision(command.decision), is_last_node)
        self.statuses[task_id] = status
        record = ApprovalDecisionRecord(task_id=task_id, approver_id=command.approver_id, decision=command.decision, comment=command.comment)
        self.records.append(record)
        return ApprovalDecisionResponse(task_id=task_id, document_status=status, record=record)
