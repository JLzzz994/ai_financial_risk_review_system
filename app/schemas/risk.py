"""风险 API 模型。"""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from engines.risk.contracts import Evidence, RiskContext, RiskFinding


class RiskEvaluationInput(BaseModel):
    """风险评估输入。"""

    amount: Decimal
    supplier_name: str
    evidence: Evidence | None = None
    currency: str = "CNY"
    invoice_total: Decimal | None = None
    line_item_total: Decimal | None = None
    contract_amount: Decimal | None = None
    payment_amount: Decimal | None = None
    batch_total: Decimal | None = None
    payment_count: int | None = None
    duplicate_account_count: int = 0
    expense_limit: Decimal | None = None
    market_unit_price: Decimal | None = None
    market_price_min: Decimal | None = None
    market_price_max: Decimal | None = None
    behavior_flags: list[str] = []
    supplier_risk_flags: list[str] = []
    required_attachment_count: int = 0
    attachment_count: int = 0
    attachment_fields_complete: bool = True
    duplicate_invoice: bool = False

    def to_context(self) -> RiskContext:
        """转换为规则引擎结构化上下文，避免 Service 传递无类型字典。"""
        return RiskContext.model_validate(self.model_dump())


class RiskEvaluationResponse(BaseModel):
    """风险评估响应。"""

    document_version_id: UUID
    findings: list[RiskFinding]


class ManualReviewRequest(BaseModel):
    """人工复核提交内容。"""

    reviewer_id: UUID
    status: str
    comment: str
    evidence: Evidence | None = None


class ManualReviewResponse(BaseModel):
    """人工复核结果。"""

    review_id: UUID
    document_version_id: UUID
    status: str
    reviewer_id: UUID | None = None
    comment: str | None = None


class RiskReviewStatusRequest(BaseModel):
    """风险项复核状态变更，与前端 PATCH 契约保持一致。"""

    review_status: str
    review_comment: str = ""
