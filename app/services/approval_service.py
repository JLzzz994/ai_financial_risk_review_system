"""审批服务，最终决定只能由分配审批人提交。"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.logging_config import get_logger, log_boundary
from app.schemas.approval import (
    ApprovalDecisionCommand,
    ApprovalDecisionRecord,
    ApprovalDecisionResponse,
    DecisionCode,
)
from engines.approval.state_machine import ApprovalDecision, next_document_status

logger = get_logger(__name__)


@dataclass
class _ApprovalSequence:
    """单个顺序审批实例的运行时状态。"""

    task_ids: tuple[UUID, ...]
    approver_ids: tuple[UUID, ...]
    current_index: int = 0
    document_status: str = "pending"


class ApprovalService:
    """固定顺序审批服务。"""

    def __init__(self) -> None:
        """初始化任务和幂等记录。"""
        self.assignees: dict[UUID, UUID] = {}
        self.statuses: dict[UUID, str] = {}
        self.records: list[ApprovalDecisionRecord] = []
        self.idempotency: set[tuple[UUID, str]] = set()
        self._sequences: dict[UUID, _ApprovalSequence] = {}
        self._task_to_sequence: dict[UUID, _ApprovalSequence] = {}
        self._idempotent_results: dict[tuple[UUID, str], ApprovalDecisionResponse] = {}

    def assign_sequence(self, approver_ids: Sequence[UUID]) -> tuple[UUID, ...]:
        """创建固定顺序审批节点，并返回按顺序生成的任务 ID。"""
        normalized = tuple(approver_ids)
        if not normalized:
            raise ValueError("审批流程至少需要一个审批节点")
        if any(not approver_id for approver_id in normalized):
            raise ValueError("审批节点必须绑定审批人")

        task_ids = tuple(uuid4() for _ in normalized)
        sequence = _ApprovalSequence(task_ids=task_ids, approver_ids=normalized)
        self._sequences[task_ids[0]] = sequence
        for task_id, approver_id in zip(task_ids, normalized, strict=True):
            self._task_to_sequence[task_id] = sequence
            self.assignees[task_id] = approver_id
            self.statuses[task_id] = "pending"
        return task_ids

    def assign(self, task_id: UUID, approver_id: UUID, is_last_node: bool = True) -> None:
        """分配顺序审批节点。"""
        if not approver_id:
            raise ValueError("审批任务必须绑定审批人")
        sequence = _ApprovalSequence(task_ids=(task_id,), approver_ids=(approver_id,))
        self._sequences[task_id] = sequence
        self._task_to_sequence[task_id] = sequence
        self.assignees[task_id] = approver_id
        self.statuses[task_id] = "pending"
        del is_last_node

    def current_task(self, task_id: UUID) -> UUID | None:
        """返回当前顺序审批实例正在等待的任务。"""
        sequence = self._task_to_sequence.get(task_id)
        if sequence is None or sequence.current_index >= len(sequence.task_ids):
            return None
        return sequence.task_ids[sequence.current_index]

    def resubmit(self, task_id: UUID) -> UUID:
        """退回后的重新提交从首节点重新开始。"""
        sequence = self._task_to_sequence.get(task_id)
        if sequence is None:
            raise ValueError("审批任务不存在")
        if sequence.document_status != "returned":
            raise ValueError("只有退回的审批实例可以重新提交")
        sequence.current_index = 0
        sequence.document_status = "pending"
        for sequence_task_id in sequence.task_ids:
            self.statuses[sequence_task_id] = "pending"
        return sequence.task_ids[0]

    async def decide(
        self,
        task_id: UUID,
        actor: UUID,
        decision: ApprovalDecision | str,
        comment: str,
        idempotency_key: str,
    ) -> ApprovalDecisionResponse:
        """异步提交审批决定，所有状态变更均经过固定顺序状态机。"""
        return self._decide(task_id, actor, decision, comment, idempotency_key)

    def _decide(
        self,
        task_id: UUID,
        actor: UUID,
        decision: ApprovalDecision | str,
        comment: str,
        idempotency_key: str,
    ) -> ApprovalDecisionResponse:
        """执行审批决定的同步核心，供兼容入口和异步入口共用。"""
        log_boundary(
            logger,
            "decide",
            "enter",
            task_id=str(task_id),
            actor_id=str(actor),
        )
        sequence = self._task_to_sequence.get(task_id)
        if sequence is None:
            raise PermissionError("只有当前节点分配的审批人可以提交决定")
        if not idempotency_key.strip():
            raise ValueError("幂等键不能为空")
        cached = self._idempotent_results.get((task_id, idempotency_key))
        if cached is not None:
            return cached
        current_task_id = self.current_task(task_id)
        if current_task_id != task_id or self.assignees.get(task_id) != actor:
            raise PermissionError("只有当前节点分配的审批人可以提交决定")
        if self.statuses.get(task_id) != "pending":
            raise ValueError("审批任务状态不允许提交决定")
        if not comment.strip():
            raise ValueError("审批决定必须填写意见")

        try:
            approval_decision = ApprovalDecision(decision)
        except ValueError as exc:
            raise ValueError("审批决定必须为 approve、return 或 reject") from exc
        is_last_node = sequence.current_index == len(sequence.task_ids) - 1
        status = next_document_status(approval_decision, is_last_node)
        self.idempotency.add((task_id, idempotency_key))

        if approval_decision is ApprovalDecision.APPROVE:
            self.statuses[task_id] = "approved"
            if not is_last_node:
                sequence.current_index += 1
                self.statuses[sequence.task_ids[sequence.current_index]] = "pending"
        else:
            sequence.document_status = status
            self.statuses[task_id] = status

        if approval_decision is ApprovalDecision.APPROVE and is_last_node:
            sequence.document_status = "approved"

        record = ApprovalDecisionRecord(
            task_id=task_id,
            approver_id=actor,
            decision=DecisionCode(approval_decision.value),
            comment=comment,
        )
        self.records.append(record)
        response = ApprovalDecisionResponse(
            task_id=task_id,
            document_status=status,
            record=record,
        )
        self._idempotent_results[(task_id, idempotency_key)] = response
        log_boundary(
            logger,
            "decide",
            "exit",
            task_id=str(task_id),
            actor_id=str(actor),
            status=status,
        )
        return response

    def submit_decision(
        self, task_id: UUID, command: ApprovalDecisionCommand, is_last_node: bool = True
    ) -> ApprovalDecisionResponse:
        """校验审批人、幂等键和任务状态后保存不可变决定。"""
        if not is_last_node and task_id not in self._task_to_sequence:
            raise ValueError("审批任务不存在")
        try:
            return self._decide(
                task_id,
                command.approver_id,
                command.decision,
                command.comment,
                command.idempotency_key,
            )
        except Exception:
            logger.exception(
                "approval operation=decide status=failed task_id=%s actor_id=%s",
                task_id,
                command.approver_id,
            )
            raise
