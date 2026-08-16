"""风险结果和证据模型。"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """风险证据，缺一项即不能形成自动结论。"""

    attachment_id: UUID
    page_or_location: str = Field(min_length=1)
    original_text: str = Field(min_length=1)
    field_name: str = Field(min_length=1)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    rule_version: str = Field(min_length=1)
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskFinding(BaseModel):
    """规则命中结果。"""

    rule_code: str
    level: str
    status: str
    message: str
    evidence: Evidence | None = None
