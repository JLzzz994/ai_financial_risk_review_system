"""审批流程模板和实例的 PostgreSQL 仓储。"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import ApprovalTask
from app.models.extended import (
    approval_instances,
    approval_workflow_nodes,
    approval_workflows,
    roles,
    user_roles,
    users,
)
from app.schemas.approval import (
    WorkflowCreateCommand,
    WorkflowNodeCommand,
    WorkflowNodeResponse,
    WorkflowPatchCommand,
    WorkflowTemplateResponse,
)


class SqlWorkflowRepository:
    """保存流程版本、顺序节点和审批实例。"""

    async def list_workflows(self, session: AsyncSession) -> list[WorkflowTemplateResponse]:
        """按更新时间倒序返回流程模板。"""
        result = await session.execute(
            select(approval_workflows).order_by(approval_workflows.c.updated_at.desc())
        )
        return [await self._to_response(session, row) for row in result.mappings().all()]

    async def get(
        self, session: AsyncSession, workflow_id: UUID
    ) -> WorkflowTemplateResponse | None:
        """查询流程模板详情。"""
        result = await session.execute(
            select(approval_workflows).where(approval_workflows.c.id == workflow_id)
        )
        row = result.mappings().first()
        return await self._to_response(session, row) if row is not None else None

    async def create(
        self, session: AsyncSession, command: WorkflowCreateCommand
    ) -> WorkflowTemplateResponse:
        """创建顺序审批流程草稿。"""
        now = datetime.now(UTC)
        workflow_id = uuid4()
        await session.execute(
            insert(approval_workflows).values(
                id=workflow_id,
                workflow_name=command.name,
                document_type=command.document_type,
                match_conditions_json={"expression": command.match_condition},
                approval_mode="sequential",
                status="draft",
                version_no=1,
                created_at=now,
                updated_at=now,
            )
        )
        await self._replace_nodes(session, workflow_id, command.nodes)
        result = await self.get(session, workflow_id)
        if result is None:
            raise ValueError("流程模板创建失败")
        return result

    async def update(
        self,
        session: AsyncSession,
        workflow_id: UUID,
        command: WorkflowPatchCommand,
    ) -> WorkflowTemplateResponse:
        """更新草稿节点和匹配条件，已发布版本不可原地修改。"""
        result = await session.execute(
            select(approval_workflows)
            .where(approval_workflows.c.id == workflow_id)
            .with_for_update()
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("流程模板不存在")
        if row["status"] == "published" and command.status != "disabled":
            raise ValueError("已发布模板不可直接修改，请新建草稿版本")
        values: dict[str, Any] = {"updated_at": datetime.now(UTC)}
        if command.name is not None:
            values["workflow_name"] = command.name
        if command.document_type is not None:
            values["document_type"] = command.document_type
        if command.match_condition is not None:
            values["match_conditions_json"] = {"expression": command.match_condition}
        if command.status is not None:
            if command.status not in {"draft", "published", "disabled"}:
                raise ValueError("流程状态不合法")
            values["status"] = command.status
        await session.execute(
            update(approval_workflows)
            .where(approval_workflows.c.id == workflow_id)
            .values(**values)
        )
        if command.nodes is not None:
            await self._replace_nodes(session, workflow_id, command.nodes)
        updated = await self.get(session, workflow_id)
        if updated is None:
            raise ValueError("流程模板不存在")
        return updated

    async def publish(
        self, session: AsyncSession, workflow_id: UUID
    ) -> WorkflowTemplateResponse:
        """发布流程模板，发布后只能新增版本。"""
        result = await session.execute(
            select(approval_workflows)
            .where(approval_workflows.c.id == workflow_id)
            .with_for_update()
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("流程模板不存在")
        node_count = await session.scalar(
            select(approval_workflow_nodes.c.id)
            .where(approval_workflow_nodes.c.workflow_id == workflow_id)
            .limit(1)
        )
        if node_count is None:
            raise ValueError("流程至少需要一个审批节点")
        await session.execute(
            update(approval_workflows)
            .where(approval_workflows.c.id == workflow_id)
            .values(
                status="published",
                published=True,
                workflow_version=row["version_no"],
                updated_at=datetime.now(UTC),
            )
        )
        published = await self.get(session, workflow_id)
        if published is None:
            raise ValueError("流程模板不存在")
        return published

    async def create_instance(
        self,
        session: AsyncSession,
        workflow_id: UUID,
        document_id: UUID,
        document_version_id: UUID,
    ) -> UUID:
        """按发布模板创建实例和全部顺序任务。"""
        workflow_result = await session.execute(
            select(approval_workflows).where(
                approval_workflows.c.id == workflow_id,
                approval_workflows.c.status == "published",
            )
        )
        workflow = workflow_result.mappings().first()
        if workflow is None:
            raise ValueError("只有已发布流程可以创建审批实例")
        nodes_result = await session.execute(
            select(approval_workflow_nodes)
            .where(approval_workflow_nodes.c.workflow_id == workflow_id)
            .order_by(approval_workflow_nodes.c.node_order)
        )
        nodes = nodes_result.mappings().all()
        if not nodes:
            raise ValueError("流程至少需要一个审批节点")
        instance_id = uuid4()
        await session.execute(
            insert(approval_instances).values(
                id=instance_id,
                workflow_id=workflow_id,
                workflow_version_no=workflow["version_no"],
                document_id=document_id,
                document_version_id=document_version_id,
                instance_status="pending",
                current_node_id=nodes[0]["id"],
                started_at=datetime.now(UTC),
            )
        )
        for node in nodes:
            approver_id = node["primary_approver_id"] or await self._resolve_approver(
                session, str(node["approver_role"])
            )
            await session.execute(
                insert(ApprovalTask).values(
                    id=uuid4(),
                    instance_id=instance_id,
                    node_id=node["id"],
                    approver_id=approver_id,
                    task_status="pending",
                    created_at=datetime.now(UTC),
                )
            )
        return instance_id

    async def find_published_for_document(
        self, session: AsyncSession, document_type: str
    ) -> UUID | None:
        """选择当前单据类型最新发布流程。"""
        result = await session.execute(
            select(approval_workflows.c.id)
            .where(
                approval_workflows.c.document_type == document_type,
                approval_workflows.c.status == "published",
            )
            .order_by(
                approval_workflows.c.version_no.desc(),
                approval_workflows.c.updated_at.desc(),
            )
            .limit(1)
        )
        value = result.scalar_one_or_none()
        return UUID(str(value)) if value is not None else None

    async def _replace_nodes(
        self,
        session: AsyncSession,
        workflow_id: UUID,
        nodes: list[WorkflowNodeCommand],
    ) -> None:
        """替换草稿节点并校验顺序唯一。"""
        if not nodes:
            raise ValueError("流程至少需要一个审批节点")
        orders = [node.order for node in nodes]
        if len(set(orders)) != len(orders):
            raise ValueError("审批节点顺序不能重复")
        await session.execute(
            delete(approval_workflow_nodes).where(
                approval_workflow_nodes.c.workflow_id == workflow_id
            )
        )
        await session.execute(
            insert(approval_workflow_nodes),
            [
                {
                    "id": uuid4(),
                    "workflow_id": workflow_id,
                    "node_name": node.name,
                    "node_order": node.order,
                    "approver_role": node.approver_role,
                    "approver_scope_json": {"names": node.approver_names},
                    "primary_approver_id": node.approver_id,
                    "approval_mode": "sequential",
                }
                for node in nodes
            ],
        )

    async def _resolve_approver(self, session: AsyncSession, role_code: str) -> UUID:
        """按节点角色选择一个启用审批人，实例创建时固化任务分配。"""
        result = await session.execute(
            select(users.c.id)
            .join(user_roles, user_roles.c.user_id == users.c.id)
            .join(roles, roles.c.id == user_roles.c.role_id)
            .where(users.c.status == "active", roles.c.role_code == role_code)
            .order_by(users.c.created_at)
            .limit(1)
        )
        approver_id = result.scalar_one_or_none()
        if approver_id is None:
            raise ValueError(f"没有可分配的审批人角色：{role_code}")
        return UUID(str(approver_id))

    async def _to_response(self, session: AsyncSession, row: Any) -> WorkflowTemplateResponse:
        """将模板和节点映射成 API 模型。"""
        result = await session.execute(
            select(approval_workflow_nodes)
            .where(approval_workflow_nodes.c.workflow_id == row["id"])
            .order_by(approval_workflow_nodes.c.node_order)
        )
        nodes = [
            WorkflowNodeResponse(
                node_id=node["id"],
                order=node["node_order"],
                name=node["node_name"],
                approver_role=node["approver_role"],
                approver_names=str((node["approver_scope_json"] or {}).get("names", "")),
                approver_id=node["primary_approver_id"],
            )
            for node in result.mappings().all()
        ]
        condition = (row["match_conditions_json"] or {}).get("expression", "")
        return WorkflowTemplateResponse(
            workflow_id=row["id"],
            name=row["workflow_name"],
            version=row["version_no"],
            document_type=row["document_type"],
            match_condition=str(condition),
            approval_mode=row["approval_mode"],
            status=row["status"],
            nodes=nodes,
            published_at=row["updated_at"] if row["status"] == "published" else None,
            updated_at=row["updated_at"],
        )


__all__ = ["SqlWorkflowRepository"]
