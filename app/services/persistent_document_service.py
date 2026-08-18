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
    DocumentLineItemCommand,
    DocumentResponse,
    DocumentVersionResponse,
)
from engines.expense_reimbursement.contracts import ExpenseLine
from engines.expense_reimbursement.validators import validate_expense_total


class PersistentDocumentService:
    """以 PostgreSQL 为事实源编排草稿、版本和明细。"""

    def __init__(self, repository: SqlDocumentRepository | None = None) -> None:
        """注入 SQL 仓储，便于测试替换。"""
        self.repository = repository or SqlDocumentRepository()

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
        return self._to_response(document)

    async def get(
        self, session: AsyncSession, actor: Principal, document_id: UUID
    ) -> DocumentResponse:
        """按申请人数据范围查询单据。"""
        document = await self.repository.get(session, document_id)
        if document is None:
            raise ValueError("单据不存在")
        self._assert_applicant(actor, document.applicant_id)
        return self._to_response(document)

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
        return DocumentVersionResponse(
            version_id=version.id,
            document_id=version.document_id,
            version_no=version.version_no,
            created_by=version.created_by,
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
        return DocumentResponse(
            document_id=document.id,
            document_no=document.document_no,
            applicant_id=document.applicant_id,
            total_amount=document.total_amount,
            currency=document.currency,
            document_status=document.document_status,
            current_version=document.current_version,
            state_version=document.document_state_version,
        )
