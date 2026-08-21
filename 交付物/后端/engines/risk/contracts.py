"""风险结果和证据模型。"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """风险证据，缺一项即不能形成自动结论。"""

    document_version_id: UUID | None = None
    attachment_id: UUID
    page_or_location: str = Field(min_length=1)
    original_text: str = Field(min_length=1)
    field_name: str = Field(min_length=1)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    rule_version: str = Field(min_length=1)
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RiskContext(BaseModel):
    """十类确定性规则共用的结构化输入，不使用无类型字典传递核心金额。"""

    amount: Decimal
    supplier_name: str
    evidence: Evidence | None = None
    invoice_total: Decimal | None = None
    line_item_total: Decimal | None = None
    contract_amount: Decimal | None = None
    payment_amount: Decimal | None = None
    batch_total: Decimal | None = None
    payment_count: int | None = Field(default=None, ge=0)
    duplicate_account_count: int = Field(default=0, ge=0)
    expense_limit: Decimal | None = None
    market_unit_price: Decimal | None = None
    market_price_min: Decimal | None = None
    market_price_max: Decimal | None = None
    behavior_flags: list[str] = Field(default_factory=list)
    supplier_risk_flags: list[str] = Field(default_factory=list)
    required_attachment_count: int = Field(default=0, ge=0)
    attachment_count: int = Field(default=0, ge=0)
    attachment_fields_complete: bool = True
    duplicate_invoice: bool = False


class RiskFinding(BaseModel):
    """规则命中结果。"""

    rule_code: str
    level: Literal["high", "medium", "low", "none"]
    status: Literal["pending", "matched", "confirmed", "dismissed", "manual_review"]
    message: str
    evidence: Evidence | None = None
    actual_value: dict[str, object] = Field(default_factory=dict)
    reference_value: dict[str, object] = Field(default_factory=dict)
    threshold: dict[str, object] = Field(default_factory=dict)
    suggestion: str | None = None

    @property
    def finding_code(self) -> str:
        """提供 SPEC 约定的 finding_code 只读别名。"""
        return self.rule_code


class AmountComparison(BaseModel):
    """同币种金额与参考区间的比较结果。"""

    actual_amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    reference_min: Decimal | None = None
    reference_max: Decimal | None = None
    difference: Decimal | None = None
    ratio: Decimal | None = None
    status: Literal["matched", "out_of_range", "reference_unavailable", "manual_review"]
    source: str | None = None
    rule_version: str


class RiskSummary(BaseModel):
    """规则汇总结果；人工复核项不能被自动提升为高风险。"""

    level: Literal["high", "medium", "low", "none"]
    manual_review_required: bool
