"""风险评估服务。"""

from uuid import UUID

from app.schemas.risk import RiskEvaluationInput, RiskEvaluationResponse
from engines.risk.rule_engine import evaluate_amount, evaluate_supplier


class RiskService:
    """编排确定性金额和供应商规则。"""

    def evaluate(self, document_version_id: UUID, data: RiskEvaluationInput) -> RiskEvaluationResponse:
        """执行规则并返回证据绑定结果。"""
        return RiskEvaluationResponse(document_version_id=document_version_id, findings=[evaluate_amount(data.amount, data.evidence), evaluate_supplier(data.supplier_name, data.evidence)])
