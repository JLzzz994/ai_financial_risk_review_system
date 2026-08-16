"""风险 API 模型。"""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from engines.risk.contracts import Evidence, RiskFinding


class RiskEvaluationInput(BaseModel):
    """风险评估输入。"""

    amount: Decimal
    supplier_name: str
    evidence: Evidence | None = None
    currency: str = "CNY"


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
