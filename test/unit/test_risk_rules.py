"""风险规则测试。"""

from decimal import Decimal
from uuid import uuid4

from engines.risk.rule_engine import aggregate_risk_level, compare_amount, evaluate_amount


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
