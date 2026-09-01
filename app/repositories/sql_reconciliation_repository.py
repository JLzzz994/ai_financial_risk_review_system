"""慧经营对账领域 PostgreSQL 仓储。"""

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reconciliation import (
    reconciliation_adjustments,
    reconciliation_cases,
    reconciliation_orders,
    reconciliation_refunds,
    reconciliation_remittances,
    reconciliation_settlements,
)
from engines.risk.reconciliation_engine import ReconciliationContext


class SqlReconciliationRepository:
    """保存和装配版本化对账数据。"""

    async def create_case(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        document_version_id: UUID,
        platform: str,
        shop_name: str,
        settlement_period: str | None,
        rule_version: str,
    ) -> UUID:
        case_id = uuid4()
        await session.execute(
            insert(reconciliation_cases).values(
                id=case_id,
                document_id=document_id,
                document_version_id=document_version_id,
                platform=platform,
                shop_name=shop_name,
                settlement_period=settlement_period,
                rule_version=rule_version,
            )
        )
        return case_id

    async def add_order(
        self,
        session: AsyncSession,
        *,
        case_id: UUID,
        document_version_id: UUID,
        order_no: str,
        expected_receivable: Decimal,
        paid_amount: Decimal | None = None,
        order_status: str | None = None,
    ) -> None:
        await session.execute(
            insert(reconciliation_orders).values(
                id=uuid4(),
                case_id=case_id,
                document_version_id=document_version_id,
                order_no=order_no,
                expected_receivable=expected_receivable,
                paid_amount=paid_amount,
                order_status=order_status,
            )
        )

    async def load_context(
        self,
        session: AsyncSession,
        *,
        document_version_id: UUID,
        order_no: str,
    ) -> ReconciliationContext:
        """按不可变版本 + 订单号装配规则所需最小上下文。"""
        case_row = (
            await session.execute(
                select(reconciliation_cases).where(
                    reconciliation_cases.c.document_version_id == document_version_id
                )
            )
        ).mappings().first()
        if case_row is None:
            raise ValueError("对账审核对象不存在")

        order_row = (
            await session.execute(
                select(reconciliation_orders).where(
                    reconciliation_orders.c.document_version_id == document_version_id,
                    reconciliation_orders.c.order_no == order_no,
                )
            )
        ).mappings().first()
        if order_row is None:
            raise ValueError("ERP 订单不存在")

        settlements = (
            await session.execute(
                select(reconciliation_settlements).where(
                    reconciliation_settlements.c.document_version_id == document_version_id,
                    reconciliation_settlements.c.order_no == order_no,
                )
            )
        ).mappings().all()
        refunds = (
            await session.execute(
                select(reconciliation_refunds).where(
                    reconciliation_refunds.c.document_version_id == document_version_id,
                    reconciliation_refunds.c.order_no == order_no,
                )
            )
        ).mappings().all()
        adjustments = (
            await session.execute(
                select(reconciliation_adjustments).where(
                    reconciliation_adjustments.c.document_version_id == document_version_id,
                    reconciliation_adjustments.c.order_no == order_no,
                )
            )
        ).mappings().all()
        remittances = (
            await session.execute(
                select(reconciliation_remittances).where(
                    reconciliation_remittances.c.document_version_id == document_version_id
                )
            )
        ).mappings().all()

        settlement_amount = sum(
            (Decimal(str(row["settlement_amount"])) for row in settlements),
            Decimal("0"),
        ) if settlements else None
        refund_amount = sum(
            (Decimal(str(row["refund_amount"])) for row in refunds), Decimal("0")
        )
        adjustment_amount = sum(
            (Decimal(str(row["adjustment_amount"])) for row in adjustments), Decimal("0")
        )
        actual_received = sum(
            (Decimal(str(row["received_amount"])) for row in remittances), Decimal("0")
        ) if remittances else None

        settlement_subject = settlements[0].get("settlement_subject") if settlements else None
        payment_subject = remittances[0].get("payment_subject") if remittances else None

        return ReconciliationContext(
            platform=str(case_row["platform"]),
            shop_name=str(case_row["shop_name"]),
            order_no=order_no,
            settlement_no=str(settlements[0]["settlement_no"]) if settlements else None,
            expected_receivable=Decimal(str(order_row["expected_receivable"])),
            platform_settlement_amount=settlement_amount,
            refund_amount=refund_amount,
            adjustment_amount=adjustment_amount,
            actual_received_amount=actual_received,
            settlement_count=len(settlements),
            refund_count=len(refunds),
            settlement_status=str(settlements[0].get("settlement_status") or "") if settlements else None,
            refund_status=str(refunds[0].get("refund_status") or "") if refunds else None,
            payment_subject=str(payment_subject) if payment_subject else None,
            settlement_subject=str(settlement_subject) if settlement_subject else None,
            adjustment_reason_present=all(bool(row.get("reason")) for row in adjustments) if adjustments else True,
            remittance_due=True,
            parsed_fields_complete=True,
            parse_confidence=None,
            evidence=None,
        )


__all__ = ["SqlReconciliationRepository"]
