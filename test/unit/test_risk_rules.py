"""风险规则测试。"""

from decimal import Decimal
from uuid import uuid4

from engines.risk.rule_engine import evaluate_amount


def test_missing_evidence_requires_manual_review() -> None:
    """证据不足不能自动形成风险结论。"""
    result = evaluate_amount(Decimal("100"), None)
    assert result.status == "manual_review"


def test_amount_threshold_with_evidence() -> None:
    """有证据时按金额阈值确定等级。"""
    from engines.risk.contracts import Evidence

    evidence = Evidence(attachment_id=uuid4(), page_or_location="p1", original_text="金额", field_name="amount", confidence=Decimal("0.99"), rule_version="v1")
    assert evaluate_amount(Decimal("10000"), evidence).level == "high"
