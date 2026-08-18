"""费用报销 PostgreSQL 仓储。"""

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import DocumentVersion, FinancialDocument
from app.models.extended import document_line_items
from app.schemas.documents import (
    DocumentLineItemCommand,
    DocumentLineItemPatch,
    DocumentLineItemResponse,
    DocumentPage,
    DocumentResponse,
    UpdateDocumentCommand,
)


@dataclass(frozen=True, slots=True)
class ExpenseLineItemRecord:
    """提交版本中需要落库的费用明细。"""

    item_name: str
    expense_date: date
    amount: Decimal
    currency: str
    remark: str | None = None


class SqlDocumentRepository:
    """使用独立异步会话访问财务单据和不可变版本。"""

    async def create_draft(
        self,
        session: AsyncSession,
        *,
        applicant_id: UUID,
        applicant_department: str,
        total_amount: Decimal,
        currency: str,
        apply_date: date,
        reason_text: str,
        document_payload: Mapping[str, Any],
    ) -> FinancialDocument:
        """创建草稿并在数据库事务中生成当天唯一单据编号。"""
        document_no = await self._next_document_no(session, apply_date)
        document = FinancialDocument(
            id=uuid4(),
            document_type="expense_reimbursement",
            document_no=document_no,
            applicant_id=applicant_id,
            applicant_department=applicant_department,
            total_amount=total_amount,
            currency=currency,
            apply_date=apply_date,
            reason_text=reason_text,
            document_payload=dict(document_payload),
            document_status="draft",
            current_version=0,
            document_state_version=1,
        )
        session.add(document)
        await session.flush()
        return document

    async def get(self, session: AsyncSession, document_id: UUID) -> FinancialDocument | None:
        """按主键查询单据。"""
        return await session.get(FinancialDocument, document_id)

    async def list_versions(
        self, session: AsyncSession, document_id: UUID
    ) -> list[DocumentVersion]:
        """按版本号升序返回不可变版本。"""
        statement = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_no.asc())
        )
        result = await session.scalars(statement)
        return list(result.all())

    async def list_documents(
        self,
        session: AsyncSession,
        applicant_id: UUID,
        *,
        page: int,
        page_size: int,
        document_type: str | None = None,
        document_status: str | None = None,
        keyword: str | None = None,
    ) -> DocumentPage:
        """按申请人范围分页查询单据。"""
        statement = select(FinancialDocument).where(FinancialDocument.applicant_id == applicant_id)
        if document_type:
            statement = statement.where(FinancialDocument.document_type == document_type)
        if document_status:
            statement = statement.where(FinancialDocument.document_status == document_status)
        if keyword:
            statement = statement.where(FinancialDocument.document_no.ilike(f"%{keyword}%"))
        statement = statement.order_by(FinancialDocument.created_at.desc())
        result = await session.scalars(statement)
        rows = list(result.all())
        total = len(rows)
        start = (page - 1) * page_size
        return DocumentPage(
            items=[self.to_response(item) for item in rows[start : start + page_size]],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_draft(
        self,
        session: AsyncSession,
        document_id: UUID,
        command: UpdateDocumentCommand,
    ) -> FinancialDocument:
        """更新草稿字段和 JSON 中的明细，提交时再固化关系明细。"""
        document = await session.scalar(
            select(FinancialDocument)
            .where(FinancialDocument.id == document_id)
            .with_for_update()
        )
        if document is None:
            raise ValueError("单据不存在")
        if document.document_state_version != command.expected_state_version:
            raise ValueError("单据已被其他请求修改")
        if document.document_status not in {"draft", "returned"}:
            raise ValueError("当前状态不可编辑")
        values = command.model_dump(exclude_unset=True)
        values.pop("expected_state_version", None)
        values.pop("line_items", None)
        line_items = command.line_items
        for field in (
            "applicant_department",
            "budget_department",
            "expense_category",
            "apply_date",
            "total_amount",
            "currency",
            "payee_name",
            "payee_account",
            "reason_text",
        ):
            if field in values:
                setattr(document, field, values[field])
        payload = deepcopy(document.document_payload)
        if line_items is not None:
            payload["line_items"] = [
                item.model_dump(mode="json")
                for item in line_items
            ]
        document.document_payload = payload
        document.document_state_version += 1
        await session.flush()
        return document

    async def copy_document(
        self, session: AsyncSession, source_id: UUID, applicant_id: UUID
    ) -> FinancialDocument:
        """复制本人单据为新草稿。"""
        source = await self.get(session, source_id)
        if source is None:
            raise ValueError("单据不存在")
        if source.applicant_id != applicant_id:
            raise ValueError("只能复制本人单据")
        document = FinancialDocument(
            id=uuid4(),
            document_type=source.document_type,
            document_no=await self._next_document_no(session, source.apply_date),
            applicant_id=applicant_id,
            applicant_department=source.applicant_department,
            budget_department=source.budget_department,
            payee_name=source.payee_name,
            payee_account=source.payee_account,
            expense_category=source.expense_category,
            total_amount=source.total_amount,
            currency=source.currency,
            apply_date=source.apply_date,
            reason_text=source.reason_text,
            document_payload=deepcopy(source.document_payload),
            document_status="draft",
            current_version=0,
            document_state_version=1,
        )
        session.add(document)
        await session.flush()
        return document

    async def change_status(
        self,
        session: AsyncSession,
        document_id: UUID,
        actor_id: UUID,
        target_status: str,
        reason: str,
    ) -> FinancialDocument:
        """在允许的状态集合内撤回或作废单据。"""
        if not reason.strip():
            raise ValueError("状态变更必须填写原因")
        document = await session.scalar(
            select(FinancialDocument)
            .where(FinancialDocument.id == document_id)
            .with_for_update()
        )
        if document is None:
            raise ValueError("单据不存在")
        if document.applicant_id != actor_id:
            raise ValueError("只能操作本人单据")
        allowed = {
            "withdrawn": {"pending_review", "reviewing", "draft"},
            "voided": {"draft", "returned", "rejected", "approved"},
        }
        if document.document_status not in allowed.get(target_status, set()):
            raise ValueError("当前状态不允许该操作")
        document.document_status = target_status
        document.document_state_version += 1
        await session.flush()
        return document

    async def list_line_items(
        self, session: AsyncSession, document_id: UUID, actor_id: UUID
    ) -> list[DocumentLineItemResponse]:
        """读取草稿 JSON 明细；提交版本的关系明细仍由版本表保存。"""
        document = await self._owned_document(session, document_id, actor_id)
        return self._payload_items(document.document_payload)

    async def add_line_item(
        self,
        session: AsyncSession,
        document_id: UUID,
        actor_id: UUID,
        item: DocumentLineItemCommand,
    ) -> DocumentLineItemResponse:
        """向可编辑单据追加明细。"""
        document = await self._owned_editable(session, document_id, actor_id)
        payload = deepcopy(document.document_payload)
        response = DocumentLineItemResponse(item_id=uuid4(), **item.model_dump())
        payload.setdefault("line_items", []).append(response.model_dump(mode="json"))
        document.document_payload = payload
        document.document_state_version += 1
        await session.flush()
        return response

    async def update_line_item(
        self,
        session: AsyncSession,
        document_id: UUID,
        item_id: UUID,
        actor_id: UUID,
        patch: DocumentLineItemPatch,
    ) -> DocumentLineItemResponse:
        """更新可编辑单据中的一条明细。"""
        document = await self._owned_editable(session, document_id, actor_id)
        payload = deepcopy(document.document_payload)
        raw_items = payload.get("line_items", [])
        for raw in raw_items:
            if str(raw.get("item_id", "")) == str(item_id):
                raw.update(patch.model_dump(exclude_unset=True))
                response = DocumentLineItemResponse.model_validate(raw)
                payload["line_items"] = [item for item in raw_items]
                document.document_payload = payload
                document.document_state_version += 1
                await session.flush()
                return response
        raise ValueError("明细不存在")

    async def delete_line_item(
        self, session: AsyncSession, document_id: UUID, item_id: UUID, actor_id: UUID
    ) -> None:
        """删除可编辑单据中的一条明细。"""
        document = await self._owned_editable(session, document_id, actor_id)
        payload = deepcopy(document.document_payload)
        raw_items = payload.get("line_items", [])
        filtered = [item for item in raw_items if str(item.get("item_id", "")) != str(item_id)]
        if len(filtered) == len(raw_items):
            raise ValueError("明细不存在")
        payload["line_items"] = filtered
        document.document_payload = payload
        document.document_state_version += 1
        await session.flush()

    async def create_version(
        self,
        session: AsyncSession,
        document: FinancialDocument,
        actor_id: UUID,
        snapshot: Mapping[str, Any],
    ) -> DocumentVersion:
        """在当前事务中创建版本快照并推进单据状态。"""
        version_no = document.current_version + 1
        version = DocumentVersion(
            id=uuid4(),
            document_id=document.id,
            version_no=version_no,
            document_snapshot_json=dict(snapshot),
            created_by=actor_id,
        )
        document.current_version = version_no
        document.document_state_version += 1
        document.document_status = "pending_review"
        session.add(version)
        await session.flush()
        return version

    async def add_version_line_items(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        document_version_id: UUID,
        line_items: Sequence[ExpenseLineItemRecord],
    ) -> None:
        """将提交快照的明细写入版本明细表。"""
        if not line_items:
            return
        rows = [
            {
                "id": uuid4(),
                "document_id": document_id,
                "document_version_id": document_version_id,
                "item_type": "expense",
                "item_name": item.item_name,
                "expense_date": item.expense_date,
                "amount": item.amount,
                "currency": item.currency,
                "remark": item.remark,
                "line_no": line_no,
            }
            for line_no, item in enumerate(line_items, start=1)
        ]
        await session.execute(document_line_items.insert(), rows)

    async def _next_document_no(self, session: AsyncSession, apply_date: date) -> str:
        """使用事务级 advisory lock 生成当天递增编号，避免并发重复。"""
        date_key = apply_date.strftime("%Y%m%d")
        lock_key = f"expense_reimbursement:{date_key}"
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": lock_key},
        )
        count_statement = select(func.count(FinancialDocument.id)).where(
            FinancialDocument.document_type == "expense_reimbursement",
            FinancialDocument.apply_date == apply_date,
        )
        count = int((await session.scalar(count_statement)) or 0)
        return f"EXP-{date_key}-{count + 1:06d}"

    async def _owned_document(
        self, session: AsyncSession, document_id: UUID, actor_id: UUID
    ) -> FinancialDocument:
        """读取并校验单据归属。"""
        document = await self.get(session, document_id)
        if document is None:
            raise ValueError("单据不存在")
        if document.applicant_id != actor_id:
            raise ValueError("只能操作本人单据")
        return document

    async def _owned_editable(
        self, session: AsyncSession, document_id: UUID, actor_id: UUID
    ) -> FinancialDocument:
        """读取本人且可编辑单据。"""
        document = await self._owned_document(session, document_id, actor_id)
        if document.document_status not in {"draft", "returned"}:
            raise ValueError("当前状态不可编辑")
        return document

    @staticmethod
    def _payload_items(payload: Mapping[str, Any]) -> list[DocumentLineItemResponse]:
        """从 JSON 载荷恢复明细模型并补齐明细 ID。"""
        items = payload.get("line_items", [])
        result: list[DocumentLineItemResponse] = []
        for item in items:
            normalized = dict(item)
            normalized.setdefault("item_id", str(uuid4()))
            result.append(DocumentLineItemResponse.model_validate(normalized))
        return result

    @staticmethod
    def to_response(document: FinancialDocument) -> DocumentResponse:
        """将 ORM 单据转换为富详情响应。"""
        return DocumentResponse(
            document_id=document.id,
            document_no=document.document_no,
            applicant_id=document.applicant_id,
            total_amount=document.total_amount,
            currency=document.currency,
            document_status=document.document_status,
            current_version=document.current_version,
            state_version=document.document_state_version,
            document_type=document.document_type,
            applicant_department=document.applicant_department,
            budget_department=document.budget_department,
            expense_category=document.expense_category,
            apply_date=document.apply_date,
            payee_name=document.payee_name,
            payee_account=document.payee_account,
            reason_text=document.reason_text,
            created_at=document.created_at.isoformat() if document.created_at else None,
            updated_at=document.updated_at.isoformat() if document.updated_at else None,
        )
