"""审批流程配置与实例创建服务。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.sql_workflow_repository import SqlWorkflowRepository
from app.schemas.approval import (
    WorkflowCreateCommand,
    WorkflowPatchCommand,
    WorkflowTemplateResponse,
)


class PersistentWorkflowService:
    """管理版本化顺序流程，禁止动态改写审批状态机。"""

    def __init__(self, repository: SqlWorkflowRepository | None = None) -> None:
        """注入流程仓储。"""
        self.repository = repository or SqlWorkflowRepository()

    async def list_workflows(
        self, session: AsyncSession
    ) -> list[WorkflowTemplateResponse]:
        """查询流程模板。"""
        return await self.repository.list_workflows(session)

    async def create(
        self, session: AsyncSession, command: WorkflowCreateCommand
    ) -> WorkflowTemplateResponse:
        """创建流程草稿。"""
        async with session.begin():
            return await self.repository.create(session, command)

    async def update(
        self,
        session: AsyncSession,
        workflow_id: UUID,
        command: WorkflowPatchCommand,
    ) -> WorkflowTemplateResponse:
        """更新流程草稿或停用已发布流程。"""
        async with session.begin():
            return await self.repository.update(session, workflow_id, command)

    async def publish(
        self, session: AsyncSession, workflow_id: UUID, reason: str
    ) -> WorkflowTemplateResponse:
        """发布流程并保留发布原因供审计层记录。"""
        if not reason.strip():
            raise ValueError("发布流程必须填写原因")
        async with session.begin():
            return await self.repository.publish(session, workflow_id)

    async def create_instance(
        self,
        session: AsyncSession,
        workflow_id: UUID,
        document_id: UUID,
        document_version_id: UUID,
    ) -> UUID:
        """按已发布模板为版本创建审批实例。"""
        async with session.begin():
            return await self.repository.create_instance(
                session, workflow_id, document_id, document_version_id
            )

    async def create_instance_for_document(
        self,
        session: AsyncSession,
        document_type: str,
        document_id: UUID,
        document_version_id: UUID,
    ) -> UUID | None:
        """按单据类型查找发布模板并创建实例；没有模板时返回空。"""
        async with session.begin():
            workflow_id = await self.repository.find_published_for_document(session, document_type)
            if workflow_id is None:
                return None
            return await self.repository.create_instance(
                session, workflow_id, document_id, document_version_id
            )


__all__ = ["PersistentWorkflowService"]
