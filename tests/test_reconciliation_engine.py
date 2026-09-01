from decimal import Decimal
from uuid import uuid4

from engines.risk.contracts import Evidence
from engines.risk.reconciliation_engine import ReconciliationContext, evaluate_reconciliation_rules


def _evidence() -> Evidence:
    return Evidence(
        attachment_id=uuid4(),
        page_or_location="sheet1!A2:H2",
        original_text="订单A，平台结算900，退款200，调整100",
        field_name="settlement_amount",
        confidence=Decimal("0.99"),
        rule_version="reconciliation-v1",
    )


def test_amount_difference_and_missing_remittance_are_high_risk() -> None:
    findings = evaluate_reconciliation_rules(
        ReconciliationContext(
            platform="tmall",
            shop_name="demo-shop",
            order_no="ORDER-001",
            settlement_no="SETTLE-001",
            expected_receivable=Decimal("1000"),
            platform_settlement_amount=Decimal("900"),
            actual_received_amount=None,
            remittance_due=True,
            settlement_subject="杭州某商贸有限公司",
            payment_subject="杭州某商贸有限公司",
            parse_confidence=Decimal("0.99"),
            evidence=_evidence(),
        )
    )
    by_code = {item.rule_code: item for item in findings}
    assert by_code["reconciliation.settlement_amount_difference"].level == "high"
    assert by_code["reconciliation.remittance_missing"].level == "high"


def test_low_confidence_parse_is_medium_risk() -> None:
    findings = evaluate_reconciliation_rules(
        ReconciliationContext(
            platform="jd",
            shop_name="demo-shop",
            order_no="ORDER-002",
            expected_receivable=Decimal("1000"),
            platform_settlement_amount=Decimal("1000"),
            actual_received_amount=Decimal("1000"),
            payment_subject="北京某科技有限公司",
            settlement_subject="北京某科技有限公司",
            parse_confidence=Decimal("0.70"),
            evidence=_evidence(),
        )
    )
    item = next(x for x in findings if x.rule_code == "reconciliation.parse_quality")
    assert item.level == "medium"
