"""金额核对、供应商和配置中心 API 模型。"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AmountRow(BaseModel):
    """金额核对明细。"""

    row_id: UUID
    source: str
    ref_no: str
    amount: Decimal
    difference: Decimal
    result: str
    note: str | None = None


class AmountComparisonResponse(BaseModel):
    """单据金额核对结果。"""

    document_id: UUID
    document_no: str
    currency: str
    document_total: Decimal
    line_item_total: Decimal
    invoice_total: Decimal
    contract_total: Decimal
    payment_total: Decimal
    invoice_rows: list[AmountRow] = Field(default_factory=list)
    contract_rows: list[AmountRow] = Field(default_factory=list)
    payment_rows: list[AmountRow] = Field(default_factory=list)


class SupplierAnomaly(BaseModel):
    """供应商历史异常。"""

    occurred_at: datetime
    document_no: str
    type: str
    description: str


class SupplierRiskResponse(BaseModel):
    """供应商风险摘要。"""

    supplier_id: UUID
    supplier_code: str
    supplier_name: str
    risk_status: str = "normal"
    tags: list[str] = Field(default_factory=list)
    blacklisted: bool = False
    blacklist_reason: str | None = None
    payment_count: int = 0
    total_paid: Decimal = Decimal("0")
    last_payment_at: datetime | None = None
    anomalies: list[SupplierAnomaly] = Field(default_factory=list)


class MarketPriceResponse(BaseModel):
    """市场价参考条目。"""

    id: UUID
    item_name: str
    specification: str | None = None
    region: str | None = None
    price_min: Decimal
    price_max: Decimal
    currency: str
    source_name: str
    effective_date: date
    status: str


class MarketPricePatch(BaseModel):
    """市场价局部更新。"""

    price_min: Decimal | None = None
    price_max: Decimal | None = None
    status: str | None = None


class RuleItemResponse(BaseModel):
    """确定性风险规则配置摘要。"""

    rule_id: str
    rule_code: str
    rule_name: str
    rule_type: str
    params: dict[str, str] = Field(default_factory=dict)
    rule_version: str
    status: str = "published"
    hit_count_30d: int = 0
    updated_at: datetime


class RulePage(BaseModel):
    """规则分页响应。"""

    items: list[RuleItemResponse]
    total: int
    page: int
    page_size: int


class RulePatch(BaseModel):
    """风险规则局部更新。"""

    status: str | None = None
    params: dict[str, str] | None = None


class RulePublishRequest(BaseModel):
    """规则发布申请。"""

    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        """拒绝只有空白字符的发布原因。"""
        value = value.strip()
        if not value:
            raise ValueError("发布原因不能为空")
        return value


class SupplierRulePatch(BaseModel):
    """供应商风险规则局部更新。"""

    enabled: bool | None = None
    threshold: Decimal | None = Field(default=None, gt=Decimal("0"))


class SystemParameterPatch(BaseModel):
    """系统参数局部更新。"""

    value: str = Field(min_length=1, max_length=500)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        """拒绝空白参数值。"""
        value = value.strip()
        if not value:
            raise ValueError("参数值不能为空")
        return value


class SupplierRuleResponse(BaseModel):
    """供应商风险规则摘要。"""

    id: str
    supplier_code: str
    supplier_name: str
    rule_name: str
    threshold: Decimal
    enabled: bool


class SystemParameterResponse(BaseModel):
    """系统参数摘要。"""

    key: str
    value: str
    description: str = ""
    updated_at: datetime
