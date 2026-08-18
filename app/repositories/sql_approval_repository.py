"""顺序审批的 PostgreSQL 仓储。"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import ApprovalTask, FinancialDocument
from app.models.extended import (
    approval_instances,
    approval_workflow_nodes,
    document_status_logs,
    users,
)
from app.schemas.approval import ApprovalHistoryNode, ApprovalTaskPage, ApprovalTaskResponse


@dataclass(slots=True)
class ApprovalDecisionContext:
    """带行锁的当前审批节点及其后继节点。"""

    task: ApprovalTask
    instance: dict[str, Any]
    node: dict[str, Any]
    next_node: dict[str, Any] | None
    next_task: ApprovalTask | None


class SqlApprovalRepository:
    """封装固定顺序审批的任务、实例和状态日志读写。"""

    async def lock_for_decision(
        self, session: AsyncSession, task_id: UUID
    ) -> ApprovalDecisionContext | None:
        """锁定当前审批任务和实例，防止并发决定推进两次。"""
        task = await session.get(ApprovalTask, task_id, with_for_update=True)
        if task is None:
            return None
        instance_result = await session.execute(
            select(approval_instances)
            .where(approval_instances.c.id == task.instance_id)
            .with_for_update()
        )
        instance_row = instance_result.mappings().first()
        if instance_row is None:
            return None
        node_result = await session.execute(
            select(approval_workflow_nodes)
            .where(approval_workflow_nodes.c.id == task.node_id)
        )
        node_row = node_result.mappings().first()
        if node_row is None:
            return None
        next_result = await session.execute(
            select(approval_workflow_nodes)
            .where(
                approval_workflow_nodes.c.workflow_id == node_row["workflow_id"],
                approval_workflow_nodes.c.node_order > node_row["node_order"],
            )
            .order_by(approval_workflow_nodes.c.node_order)
            .limit(1)
        )
        next_node = next_result.mappings().first()
        next_task: ApprovalTask | None = None
        if next_node is not None:
            next_task = await session.scalar(
                select(ApprovalTask)
                .where(
                    ApprovalTask.instance_id == task.instance_id,
                    ApprovalTask.node_id == next_node["id"],
                )
                .with_for_update()
            )
        return ApprovalDecisionContext(
            task=task,
            instance=dict(instance_row),
            node=dict(node_row),
            next_node=dict(next_node) if next_node is not None else None,
            next_task=next_task,
        )

    async def apply_decision(
        self,
        session: AsyncSession,
        context: ApprovalDecisionContext,
        *,
        decision: str,
        document_status: str,
        comment: str,
        actor_id: UUID,
    ) -> None:
        """在当前事务写入任务、实例、单据状态和状态日志。"""
        task = context.task
        task.task_status = "approved" if decision == "approve" else document_status
        task.decision = decision
        task.review_comment = comment
        task.processed_at = datetime.now(UTC)

        instance_id = context.instance["id"]
        if decision == "approve" and context.next_node is not None and context.next_task:
            context.next_task.task_status = "pending"
            await session.execute(
                approval_instances.update()
                .where(approval_instances.c.id == instance_id)
                .values(current_node_id=context.next_node["id"])
            )
        else:
            await session.execute(
                approval_instances.update()
                .where(approval_instances.c.id == instance_id)
                .values(
                    instance_status=document_status,
                    finished_at=datetime.now(UTC),
                )
            )

        await session.execute(
            update(FinancialDocument)
            .where(FinancialDocument.id == context.instance["document_id"])
            .values(
                document_status=document_status,
                document_state_version=FinancialDocument.document_state_version + 1,
            )
        )
        await session.execute(
            document_status_logs.insert().values(
                id=uuid4(),
                document_id=context.instance["document_id"],
                document_version_id=context.instance["document_version_id"],
                from_status="pending_approval",
                to_status=document_status,
                operator_id=actor_id,
                remark=comment,
            )
        )

    async def get_view(
        self, session: AsyncSession, task_id: UUID
    ) -> ApprovalTaskResponse | None:
        """查询审批任务详情及单据摘要。"""
        rows = await self._query_views(session, task_id=task_id)
        return rows[0] if rows else None

    async def list_for_approver(
        self,
        session: AsyncSession,
        approver_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
        task_status: str | None = None,
    ) -> ApprovalTaskPage:
        """只查询分配给当前审批人的任务。"""
        rows = await self._query_views(session, approver_id=approver_id, task_status=task_status)
        total = len(rows)
        start = (page - 1) * page_size
        return ApprovalTaskPage(
            items=rows[start : start + page_size],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def list_history(
        self, session: AsyncSession, document_id: UUID
    ) -> list[ApprovalHistoryNode]:
        """按节点顺序返回单据审批历史。"""
        approver = users.alias("history_approver")
        statement = (
            select(
                approval_workflow_nodes.c.node_order,
                approval_workflow_nodes.c.node_name,
                approver.c.display_name.label("assignee_name"),
                ApprovalTask.task_status,
                ApprovalTask.decision,
                ApprovalTask.review_comment,
                ApprovalTask.processed_at,
            )
            .select_from(ApprovalTask.__table__)
            .join(
                approval_instances,
                ApprovalTask.instance_id == approval_instances.c.id,
            )
            .join(
                approval_workflow_nodes,
                ApprovalTask.node_id == approval_workflow_nodes.c.id,
            )
            .join(approver, ApprovalTask.approver_id == approver.c.id)
            .where(approval_instances.c.document_id == document_id)
            .order_by(approval_workflow_nodes.c.node_order)
        )
        result = await session.execute(statement)
        return [ApprovalHistoryNode.model_validate(row) for row in result.mappings().all()]

    async def _query_views(
        self,
        session: AsyncSession,
        *,
        task_id: UUID | None = None,
        approver_id: UUID | None = None,
        task_status: str | None = None,
    ) -> list[ApprovalTaskResponse]:
        """查询任务视图，避免路由直接拼接多表 SQL。"""
        approver = users.alias("task_approver")
        applicant = users.alias("task_applicant")
        statement = (
            select(
                ApprovalTask.id.label("task_id"),
                approval_instances.c.document_id,
                approval_instances.c.document_version_id,
                approval_workflow_nodes.c.id.label("node_id"),
                approval_workflow_nodes.c.node_name,
                approval_workflow_nodes.c.node_order,
                ApprovalTask.approver_id.label("assignee_id"),
                approver.c.display_name.label("assignee_name"),
                ApprovalTask.task_status,
                ApprovalTask.decision,
                ApprovalTask.review_comment,
                ApprovalTask.created_at,
                ApprovalTask.processed_at,
                FinancialDocument.document_no,
                FinancialDocument.document_type,
                FinancialDocument.total_amount,
                FinancialDocument.currency,
                FinancialDocument.applicant_department,
                applicant.c.display_name.label("applicant_name"),
            )
            .select_from(ApprovalTask.__table__)
            .join(approval_instances, ApprovalTask.instance_id == approval_instances.c.id)
            .join(approval_workflow_nodes, ApprovalTask.node_id == approval_workflow_nodes.c.id)
            .join(FinancialDocument, FinancialDocument.id == approval_instances.c.document_id)
            .join(approver, ApprovalTask.approver_id == approver.c.id)
            .join(applicant, FinancialDocument.applicant_id == applicant.c.id)
        )
        if task_id is not None:
            statement = statement.where(ApprovalTask.id == task_id)
        if approver_id is not None:
            statement = statement.where(ApprovalTask.approver_id == approver_id)
        if task_status is not None:
            statement = statement.where(ApprovalTask.task_status == task_status)
        statement = statement.order_by(ApprovalTask.created_at.desc())
        result = await session.execute(statement)
        return [
            ApprovalTaskResponse(
                task_id=row["task_id"],
                document_id=row["document_id"],
                document_no=row["document_no"],
                document_type=row["document_type"],
                node_id=row["node_id"],
                node_name=row["node_name"],
                node_order=row["node_order"],
                assignee_id=row["assignee_id"],
                assignee_name=row["assignee_name"],
                task_status=row["task_status"],
                decision=row["decision"],
                review_comment=row["review_comment"],
                total_amount=row["total_amount"],
                currency=row["currency"],
                applicant_name=row["applicant_name"],
                applicant_department=row["applicant_department"],
                created_at=row["created_at"],
                processed_at=row["processed_at"],
            )
            for row in result.mappings().all()
        ]


__all__ = ["ApprovalDecisionContext", "SqlApprovalRepository"]
