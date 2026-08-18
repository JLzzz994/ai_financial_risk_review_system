"""费用报销 PostgreSQL 仓储。"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import DocumentVersion, FinancialDocument
from app.models.extended import document_line_items


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
