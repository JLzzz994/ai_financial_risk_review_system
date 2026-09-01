from decimal import Decimal
from uuid import uuid4

from engines.model.explanation_contracts import ExplanationRequest, ExplanationResult
from engines.risk.contracts import Evidence
from engines.risk.reconciliation_engine import (
    ReconciliationContext,
    evaluate_reconciliation_rules,
)


class FakeExplanationAdapter:
    async def explain(self, request: ExplanationRequest) -> ExplanationResult:
        # 适配器只能返回文本，无法返回新的 risk_level / finding_status。
        assert request.rule_code == "reconciliation.settlement_amount_difference"
        assert request.risk_level == "high"
        assert request.finding_status == "matched"
        return ExplanationResult(
            explanation="平台结算金额与规则计算的应结金额存在差异。",
            suggestion="核对退款、手续费和平台调整项后人工确认。",
            model_version="fake-llm",
            prompt_version="reconciliation-explain-v1",
        )


def _evidence() -> Evidence:
    return Evidence(
        attachment_id=uuid4(),
        page_or_location="sheet1!A2:H2",
        original_text="订单 ORDER-001 平台结算 1180",
        field_name="settlement_amount",
        confidence=Decimal("0.99"),
        rule_version="reconciliation-v1",
    )


def test_rule_fact_is_fixed_before_explanation() -> None:
    findings = evaluate_reconciliation_rules(
        ReconciliationContext(
            platform="tmall",
            shop_name="demo",
            order_no="ORDER-001",
            expected_receivable=Decimal("1280"),
            platform_settlement_amount=Decimal("1180"),
            actual_received_amount=Decimal("1180"),
            payment_subject="A公司",
            settlement_subject="A公司",
            parse_confidence=Decimal("0.99"),
            evidence=_evidence(),
        )
    )
    finding = next(
        item
        for item in findings
        if item.rule_code == "reconciliation.settlement_amount_difference"
    )
    assert finding.level == "high"
    assert finding.status == "matched"
    assert finding.reference_value["difference"] == Decimal("-100")
