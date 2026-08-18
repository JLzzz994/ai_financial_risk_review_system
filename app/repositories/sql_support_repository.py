"""金额核对和供应商资料查询仓储。"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import FinancialDocument
from app.models.extended import document_line_items, market_price_references, supplier_profiles
from app.schemas.support import (
    AmountComparisonResponse,
    AmountRow,
    MarketPricePatch,
    MarketPriceResponse,
    SupplierRiskResponse,
)


class SqlSupportRepository:
    """访问市场价格、供应商资料和金额核对所需关系表。"""

    async def amount_comparison(
        self, session: AsyncSession, document_id: UUID
    ) -> AmountComparisonResponse:
        """按单据和版本明细计算金额差异。"""
        document = await session.get(FinancialDocument, document_id)
        if document is None:
            raise ValueError("单据不存在")
        result = await session.execute(
            select(document_line_items)
            .where(document_line_items.c.document_id == document_id)
            .order_by(document_line_items.c.line_no)
        )
        rows = result.mappings().all()
        line_total = sum((Decimal(str(row["amount"])) for row in rows), Decimal("0"))
        line_rows = [
            AmountRow(
                row_id=row["id"],
                source="line_item",
                ref_no=str(row["line_no"]),
                amount=row["amount"],
                difference=row["amount"] - document.total_amount,
                result="match" if row["amount"] == document.total_amount else "mismatch",
            )
            for row in rows
        ]
        return AmountComparisonResponse(
            document_id=document.id,
            document_no=document.document_no,
            currency=document.currency,
            document_total=document.total_amount,
            line_item_total=line_total,
            invoice_total=document.total_amount,
            contract_total=document.total_amount,
            payment_total=document.total_amount,
            invoice_rows=line_rows,
            contract_rows=[],
            payment_rows=[],
        )

    async def supplier_by_code(
        self, session: AsyncSession, supplier_code: str
    ) -> SupplierRiskResponse:
        """按供应商编码查询风险摘要。"""
        result = await session.execute(
            select(supplier_profiles).where(supplier_profiles.c.supplier_code == supplier_code)
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("供应商不存在")
        tags = (row["risk_tags_json"] or {}).get("tags", [])
        blacklisted = str(row["blacklist_status"]) == "blacklisted"
        return SupplierRiskResponse(
            supplier_id=row["id"],
            supplier_code=row["supplier_code"],
            supplier_name=row["supplier_name"],
            risk_status="blacklisted" if blacklisted else str(row.get("credit_status") or "normal"),
            tags=[str(tag) for tag in tags],
            blacklisted=blacklisted,
            blacklist_reason=(row["risk_tags_json"] or {}).get("blacklist_reason"),
            payment_count=int((row["historical_risk_json"] or {}).get("payment_count", 0)),
            total_paid=Decimal(str((row["historical_risk_json"] or {}).get("total_paid", "0"))),
            last_payment_at=None,
            anomalies=[],
        )

    async def supplier_by_id(
        self, session: AsyncSession, supplier_id: UUID
    ) -> SupplierRiskResponse:
        """按供应商 ID 查询风险摘要。"""
        result = await session.execute(
            select(supplier_profiles.c.supplier_code).where(supplier_profiles.c.id == supplier_id)
        )
        code = result.scalar_one_or_none()
        if code is None:
            raise ValueError("供应商不存在")
        return await self.supplier_by_code(session, str(code))

    async def list_market_prices(
        self, session: AsyncSession, keyword: str | None = None
    ) -> list[MarketPriceResponse]:
        """查询市场价格参考。"""
        statement = select(market_price_references).order_by(
            market_price_references.c.effective_date.desc()
        )
        if keyword:
            statement = statement.where(
                market_price_references.c.item_name.ilike(f"%{keyword}%")
            )
        result = await session.execute(statement)
        return [self._market_price(row) for row in result.mappings().all()]

    async def update_market_price(
        self, session: AsyncSession, price_id: UUID, patch: MarketPricePatch
    ) -> MarketPriceResponse:
        """更新市场价格参考。"""
        values = patch.model_dump(exclude_unset=True)
        if not values:
            raise ValueError("没有需要更新的字段")
        await session.execute(
            update(market_price_references)
            .where(market_price_references.c.id == price_id)
            .values(**values, updated_at=datetime.now(UTC))
        )
        result = await session.execute(
            select(market_price_references).where(market_price_references.c.id == price_id)
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("市场价条目不存在")
        return self._market_price(row)

    @staticmethod
    def _market_price(row: Any) -> MarketPriceResponse:
        """映射市场价表行。"""
        return MarketPriceResponse(
            id=row["id"],
            item_name=row["item_name"],
            specification=row.get("specification"),
            region=row.get("region"),
            price_min=row["price_min"],
            price_max=row["price_max"],
            currency=row["currency"],
            source_name=row["source_name"],
            effective_date=row["effective_date"],
            status=row["status"],
        )


__all__ = ["SqlSupportRepository"]
