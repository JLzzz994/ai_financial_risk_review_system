"""电商对账异常审核服务。"""

from uuid import UUID

from app.schemas.reconciliation import ReconciliationEvaluationInput, ReconciliationEvaluationResponse
from engines.risk.reconciliation_engine import evaluate_reconciliation_rules


class ReconciliationService:
    """只编排确定性对账规则，不调用 LLM。"""

    def evaluate(
        self,
        document_version_id: UUID,
        data: ReconciliationEvaluationInput,
    ) -> ReconciliationEvaluationResponse:
        findings = evaluate_reconciliation_rules(data.to_context())
        return ReconciliationEvaluationResponse(
            document_version_id=document_version_id,
            findings=findings,
        )
