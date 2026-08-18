"""费用报销 PostgreSQL 应用服务。"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AuthorizationError
from app.repositories.sql_document_repository import (
    ExpenseLineItemRecord,
    SqlDocumentRepository,
)
from app.schemas.auth import Principal
from app.schemas.documents import (
    CreateDocumentCommand,
    DocumentActionCommand,
    DocumentLineItemCommand,
    DocumentLineItemPatch,
    DocumentLineItemResponse,
    DocumentPage,
    DocumentResponse,
    DocumentVersionResponse,
    UpdateDocumentCommand,
)
from app.services.persistent_analysis_service import PersistentAnalysisService
from app.services.persistent_workflow_service import PersistentWorkflowService
from engines.expense_reimbursement.contracts import ExpenseLine
from engines.expense_reimbursement.validators import validate_expense_total


class PersistentDocumentService:
    """以 PostgreSQL 为事实源编排草稿、版本和明细。"""

    def __init__(
        self,
        repository: SqlDocumentRepository | None = None,
        analysis_service: PersistentAnalysisService | None = None,
        workflow_service: PersistentWorkflowService | None = None,
    ) -> None:
        """注入 SQL 仓储，便于测试替换。"""
        self.repository = repository or SqlDocumentRepository()
        self.analysis_service = analysis_service or PersistentAnalysisService()
        self.workflow_service = workflow_service or PersistentWorkflowService()

    async def create_draft(
        self,
        session: AsyncSession,
        actor: Principal,
        command: CreateDocumentCommand,
    ) -> DocumentResponse:
        """创建费用报销草稿，草稿明细暂存载荷，提交时固化到明细表。"""
        self._assert_applicant(actor, command.applicant_id)
        lines = self._to_domain_lines(command.line_items)
        if lines:
            validate_expense_total(command.total_amount, lines, command.currency)
        payload: dict[str, Any] = {
            "line_items": [item.model_dump(mode="json") for item in command.line_items]
        }
        async with session.begin():
            document = await self.repository.create_draft(
                session,
                applicant_id=command.applicant_id,
                applicant_department=command.applicant_department,
                total_amount=command.total_amount,
                currency=command.currency,
                apply_date=command.apply_date,
                reason_text=command.reason_text,
                document_payload=payload,
            )
        return self.repository.to_response(document)

    async def get(
        self, session: AsyncSession, actor: Principal, document_id: UUID
    ) -> DocumentResponse:
        """按申请人数据范围查询单据。"""
        document = await self.repository.get(session, document_id)
        if document is None:
            raise ValueError("单据不存在")
        self._assert_applicant(actor, document.applicant_id)
        return self.repository.to_response(document)

    async def list_documents(
        self,
        session: AsyncSession,
        actor: Principal,
        *,
        page: int,
        page_size: int,
        document_type: str | None = None,
        document_status: str | None = None,
        keyword: str | None = None,
    ) -> DocumentPage:
        """按本人范围分页查询单据。"""
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("分页参数不合法")
        return await self.repository.list_documents(
            session,
            actor.user_id,
            page=page,
            page_size=page_size,
            document_type=document_type,
            document_status=document_status,
            keyword=keyword,
        )

    async def update_draft(
        self,
        session: AsyncSession,
        actor: Principal,
        document_id: UUID,
        command: UpdateDocumentCommand,
    ) -> DocumentResponse:
        """更新本人草稿或退回单据。"""
        async with session.begin():
            document = await self.repository.get(session, document_id)
            if document is None:
                raise ValueError("单据不存在")
            self._assert_applicant(actor, document.applicant_id)
            updated = await self.repository.update_draft(session, document_id, command)
        return self.repository.to_response(updated)

    async def copy(
        self, session: AsyncSession, actor: Principal, document_id: UUID
    ) -> DocumentResponse:
        """复制本人单据为新草稿。"""
        async with session.begin():
            document = await self.repository.copy_document(session, document_id, actor.user_id)
        return self.repository.to_response(document)

    async def change_status(
        self,
        session: AsyncSession,
        actor: Principal,
        document_id: UUID,
        command: DocumentActionCommand,
        target_status: str,
    ) -> None:
        """撤回或作废本人单据。"""
        async with session.begin():
            await self.repository.change_status(
                session, document_id, actor.user_id, target_status, command.reason
            )

    async def list_line_items(
        self, session: AsyncSession, actor: Principal, document_id: UUID
    ) -> list[DocumentLineItemResponse]:
        """查询本人单据明细。"""
        return await self.repository.list_line_items(session, document_id, actor.user_id)

    async def add_line_item(
        self,
        session: AsyncSession,
        actor: Principal,
        document_id: UUID,
        item: DocumentLineItemCommand,
    ) -> DocumentLineItemResponse:
        """新增本人草稿明细。"""
        async with session.begin():
            return await self.repository.add_line_item(session, document_id, actor.user_id, item)

    async def update_line_item(
        self,
        session: AsyncSession,
        actor: Principal,
        document_id: UUID,
        item_id: UUID,
        patch: DocumentLineItemPatch,
    ) -> DocumentLineItemResponse:
        """更新本人草稿明细。"""
        async with session.begin():
            return await self.repository.update_line_item(
                session, document_id, item_id, actor.user_id, patch
            )

    async def delete_line_item(
        self, session: AsyncSession, actor: Principal, document_id: UUID, item_id: UUID
    ) -> None:
        """删除本人草稿明细。"""
        async with session.begin():
            await self.repository.delete_line_item(session, document_id, item_id, actor.user_id)

    async def list_versions(
        self, session: AsyncSession, actor: Principal, document_id: UUID
    ) -> list[DocumentVersionResponse]:
        """查询指定单据的不可变版本历史。"""
        document = await self.repository.get(session, document_id)
        if document is None:
            raise ValueError("单据不存在")
        self._assert_applicant(actor, document.applicant_id)
        versions = await self.repository.list_versions(session, document_id)
        return [
            DocumentVersionResponse(
                version_id=version.id,
                document_id=version.document_id,
                version_no=version.version_no,
                created_by=version.created_by,
            )
            for version in versions
        ]

    async def submit(
        self,
        session: AsyncSession,
        actor: Principal,
        document_id: UUID,
        expected_state_version: int,
        idempotency_key: str | None = None,
    ) -> DocumentVersionResponse:
        """提交草稿，固化版本快照并落库版本明细。"""
        async with session.begin():
            document = await self.repository.get(session, document_id)
            if document is None:
                raise ValueError("单据不存在")
            self._assert_applicant(actor, document.applicant_id)
            if document.document_state_version != expected_state_version:
                raise ValueError("单据已被其他请求修改")
            if document.document_status not in {"draft", "returned"}:
                raise ValueError("当前状态不可提交")
            line_commands = self._payload_lines(document.document_payload)
            lines = self._to_domain_lines(line_commands)
            validate_expense_total(document.total_amount, lines, document.currency)
            snapshot = self._snapshot(document, line_commands)
            version = await self.repository.create_version(
                session, document, actor.user_id, snapshot
            )
            records = [
                ExpenseLineItemRecord(
                    item_name=item.expense_item,
                    expense_date=item.expense_date,
                    amount=item.amount,
                    currency=item.currency,
                    remark=item.remark,
                )
                for item in line_commands
            ]
            await self.repository.add_version_line_items(
                session,
                document_id=document.id,
                document_version_id=version.id,
                line_items=records,
            )
        analysis_task_id: UUID | None = None
        if idempotency_key:
            analysis_task = await self.analysis_service.start(
                session, version.document_id, version.id, idempotency_key
            )
            analysis_task_id = analysis_task.task_id
            await self.workflow_service.create_instance_for_document(
                session,
                "expense_reimbursement",
                version.document_id,
                version.id,
            )
        return DocumentVersionResponse(
            version_id=version.id,
            document_id=version.document_id,
            version_no=version.version_no,
            created_by=version.created_by,
            document_version_id=version.id,
            analysis_task_id=analysis_task_id,
            status="pending_review",
        )

    @staticmethod
    def _assert_applicant(actor: Principal, applicant_id: UUID) -> None:
        """只允许申请人操作本人单据。"""
        if actor.user_id != applicant_id:
            raise AuthorizationError("只能操作本人费用报销单")

    @staticmethod
    def _to_domain_lines(items: Sequence[DocumentLineItemCommand]) -> tuple[ExpenseLine, ...]:
        """将 API 明细模型转换为领域对象。"""
        return tuple(ExpenseLine(item.expense_item, item.amount, item.currency) for item in items)

    @staticmethod
    def _payload_lines(payload: dict[str, Any]) -> list[DocumentLineItemCommand]:
        """从草稿载荷恢复明细模型，提交前再次执行 Pydantic 校验。"""
        raw_items = payload.get("line_items", [])
        if not isinstance(raw_items, list):
            raise ValueError("草稿明细载荷格式错误")
        return [DocumentLineItemCommand.model_validate(item) for item in raw_items]

    @staticmethod
    def _snapshot(document: Any, line_items: Sequence[DocumentLineItemCommand]) -> dict[str, Any]:
        """构造不可变版本快照，不保存对象存储绝对路径。"""
        return {
            "document_type": document.document_type,
            "document_no": document.document_no,
            "applicant_id": str(document.applicant_id),
            "applicant_department": document.applicant_department,
            "total_amount": str(document.total_amount),
            "currency": document.currency,
            "apply_date": document.apply_date.isoformat(),
            "reason_text": document.reason_text,
            "line_items": [item.model_dump(mode="json") for item in line_items],
        }

    @staticmethod
    def _to_response(document: Any) -> DocumentResponse:
        """将 ORM 对象转换为 API 响应模型。"""
        return SqlDocumentRepository.to_response(document)
