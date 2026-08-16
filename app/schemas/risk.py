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


class RiskEvaluationResponse(BaseModel):
    """风险评估响应。"""

    document_version_id: UUID
    findings: list[RiskFinding]
