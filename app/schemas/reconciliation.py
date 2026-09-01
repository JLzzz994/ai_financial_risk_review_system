"""电商对账异常审核 API 模型。"""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from engines.risk.contracts import Evidence, RiskFinding
from engines.risk.reconciliation_engine import ReconciliationContext


class ReconciliationEvaluationInput(BaseModel):
    platform: str
    shop_name: str
    order_no: str
    settlement_no: str | None = None
    expected_receivable: Decimal
    platform_settlement_amount: Decimal | None = None
    refund_amount: Decimal = Decimal("0")
    adjustment_amount: Decimal = Decimal("0")
    actual_received_amount: Decimal | None = None
    settlement_count: int = Field(default=1, ge=0)
    refund_count: int = Field(default=0, ge=0)
    settlement_status: str | None = None
    refund_status: str | None = None
    payment_subject: str | None = None
    settlement_subject: str | None = None
    adjustment_reason_present: bool = True
    remittance_due: bool = False
    parsed_fields_complete: bool = True
    parse_confidence: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    evidence: Evidence | None = None
    tolerance: Decimal = Decimal("0.01")
    adjustment_threshold: Decimal = Decimal("1000")
    low_confidence_threshold: Decimal = Decimal("0.85")

    def to_context(self) -> ReconciliationContext:
        return ReconciliationContext.model_validate(self.model_dump())


class ReconciliationEvaluationResponse(BaseModel):
    document_version_id: UUID
    findings: list[RiskFinding]
