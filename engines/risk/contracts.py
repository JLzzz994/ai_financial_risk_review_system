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


class RiskFinding(BaseModel):
    """规则命中结果。"""

    rule_code: str
    level: Literal["high", "medium", "low", "none"]
    status: Literal["pending", "matched", "confirmed", "dismissed", "manual_review"]
    message: str
    evidence: Evidence | None = None

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
