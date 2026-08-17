"""风险规则测试。"""

from decimal import Decimal
from uuid import uuid4

from engines.risk.contracts import Evidence, RiskContext
from engines.risk.rule_engine import (
    aggregate_risk_level,
    compare_amount,
    evaluate_amount,
    evaluate_ten_rules,
)


def test_missing_evidence_requires_manual_review() -> None:
    """证据不足不能自动形成风险结论。"""
    result = evaluate_amount(Decimal("100"), None)
    assert result.status == "manual_review"


def test_amount_threshold_with_evidence() -> None:
    """有证据时按金额阈值确定等级。"""
    from engines.risk.contracts import Evidence

    evidence = Evidence(
        attachment_id=uuid4(),
        page_or_location="p1",
        original_text="金额",
        field_name="amount",
        confidence=Decimal("0.99"),
        rule_version="v1",
    )
    assert evaluate_amount(Decimal("10000"), evidence).level == "high"


def test_amount_comparison_does_not_convert_currency() -> None:
    """金额参考数据缺失时返回 reference_unavailable。"""
    result = compare_amount(Decimal("100"), "CNY", None, None, "v1")
    assert result.status == "reference_unavailable"


def test_manual_review_is_not_automatically_high_risk() -> None:
    """证据不足只要求人工处理，不直接提升综合等级。"""
    finding = evaluate_amount(Decimal("10000"), None)
    summary = aggregate_risk_level([finding])
    assert summary.level == "none"
    assert summary.manual_review_required is True


def test_ten_deterministic_risk_rules_return_auditable_codes() -> None:
    """完整输入时十类规则均输出稳定编码和证据。"""
    evidence = Evidence(
        attachment_id=uuid4(),
        page_or_location="invoice:p1",
        original_text="财务凭证原文片段",
        field_name="amount",
        confidence=Decimal("0.99"),
        rule_version="risk-v1",
    )
    context = RiskContext(
        amount=Decimal("12000"),
        supplier_name="异常供应商",
        evidence=evidence,
        invoice_total=Decimal("10000"),
        line_item_total=Decimal("12000"),
        contract_amount=Decimal("10000"),
        payment_amount=Decimal("12000"),
        batch_total=Decimal("12000"),
        payment_count=2,
        duplicate_account_count=1,
        expense_limit=Decimal("10000"),
        market_unit_price=Decimal("120"),
        market_price_min=Decimal("80"),
        market_price_max=Decimal("100"),
        behavior_flags=["same_day_duplicate"],
        supplier_risk_flags=["blacklist"],
        required_attachment_count=2,
        attachment_count=1,
        attachment_fields_complete=False,
        duplicate_invoice=True,
    )

    findings = evaluate_ten_rules(context)

    assert len(findings) == 10
    assert {finding.rule_code for finding in findings} == {
        "document.invoice_amount_consistency",
        "line_items.total_consistency",
        "contract.payment_consistency",
        "batch_payment.consistency",
        "expense.standard_compliance",
        "market_price.reasonableness",
        "behavior.anomaly",
        "supplier.risk",
        "attachment.completeness",
        "invoice.duplicate",
    }
    assert all(finding.evidence == evidence for finding in findings)


def test_ten_rules_without_evidence_require_manual_review() -> None:
    """任何规则缺少完整证据时都不能形成自动风险结论。"""
    context = RiskContext(amount=Decimal("100"), supplier_name="供应商")

    findings = evaluate_ten_rules(context)

    assert len(findings) == 10
    assert {finding.status for finding in findings} == {"manual_review"}
