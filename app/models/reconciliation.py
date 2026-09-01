"""慧经营电商对账领域数据模型。

结构化记录全部绑定不可变 document_version_id；原始账单附件及 OCR 证据仍由
``document_attachments`` / ``attachment_parse_results`` 保存，避免重复存储原文。
"""

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)

from app.models.base import Base


def _id() -> Column:
    return Column("id", Uuid, primary_key=True, default=uuid4)


def _created_at() -> Column:
    return Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    )


reconciliation_cases = Table(
    "reconciliation_cases",
    Base.metadata,
    _id(),
    Column("document_id", Uuid, ForeignKey("financial_documents.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("platform", String(32), nullable=False),
    Column("shop_name", String(128), nullable=False),
    Column("settlement_period", String(64)),
    Column("rule_version", String(64), nullable=False, server_default="reconciliation-v1"),
    Column("case_status", String(32), nullable=False, server_default="pending"),
    _created_at(),
    UniqueConstraint("document_version_id", name="uq_reconciliation_cases_version"),
)

reconciliation_orders = Table(
    "reconciliation_orders",
    Base.metadata,
    _id(),
    Column("case_id", Uuid, ForeignKey("reconciliation_cases.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("order_no", String(128), nullable=False),
    Column("expected_receivable", Numeric(18, 2), nullable=False),
    Column("paid_amount", Numeric(18, 2)),
    Column("order_status", String(32)),
    Column("currency", String(3), nullable=False, server_default="CNY"),
    _created_at(),
    UniqueConstraint("case_id", "order_no", name="uq_reconciliation_orders_case_order"),
)

reconciliation_settlements = Table(
    "reconciliation_settlements",
    Base.metadata,
    _id(),
    Column("case_id", Uuid, ForeignKey("reconciliation_cases.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("order_no", String(128), nullable=False),
    Column("settlement_no", String(128), nullable=False),
    Column("settlement_amount", Numeric(18, 2), nullable=False),
    Column("fee_amount", Numeric(18, 2), nullable=False, server_default="0"),
    Column("adjustment_amount", Numeric(18, 2), nullable=False, server_default="0"),
    Column("settlement_subject", String(255)),
    Column("settlement_status", String(32)),
    _created_at(),
    Index("ix_reconciliation_settlements_order_no", "order_no"),
    Index("ix_reconciliation_settlements_settlement_no", "settlement_no"),
)

reconciliation_refunds = Table(
    "reconciliation_refunds",
    Base.metadata,
    _id(),
    Column("case_id", Uuid, ForeignKey("reconciliation_cases.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("order_no", String(128), nullable=False),
    Column("refund_no", String(128), nullable=False),
    Column("refund_amount", Numeric(18, 2), nullable=False),
    Column("refund_status", String(32)),
    _created_at(),
    UniqueConstraint("case_id", "refund_no", name="uq_reconciliation_refunds_case_refund"),
)

reconciliation_adjustments = Table(
    "reconciliation_adjustments",
    Base.metadata,
    _id(),
    Column("case_id", Uuid, ForeignKey("reconciliation_cases.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("order_no", String(128)),
    Column("adjustment_type", String(64), nullable=False),
    Column("adjustment_amount", Numeric(18, 2), nullable=False),
    Column("reason", Text),
    Column("evidence_present", Boolean, nullable=False, server_default="false"),
    _created_at(),
)

reconciliation_remittances = Table(
    "reconciliation_remittances",
    Base.metadata,
    _id(),
    Column("case_id", Uuid, ForeignKey("reconciliation_cases.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("remittance_no", String(128), nullable=False),
    Column("received_amount", Numeric(18, 2), nullable=False),
    Column("received_at", DateTime(timezone=True)),
    Column("payment_subject", String(255)),
    _created_at(),
    UniqueConstraint(
        "case_id", "remittance_no", name="uq_reconciliation_remittances_case_no"
    ),
)

RECONCILIATION_TABLE_NAMES = (
    "reconciliation_cases",
    "reconciliation_orders",
    "reconciliation_settlements",
    "reconciliation_refunds",
    "reconciliation_adjustments",
    "reconciliation_remittances",
)

__all__ = ["RECONCILIATION_TABLE_NAMES"]
