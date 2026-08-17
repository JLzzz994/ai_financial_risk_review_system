"""确定性风险规则执行器。

规则模块只生成风险事实，不接触审批状态，也不调用 LLM。
"""

from collections.abc import Iterable
from decimal import Decimal
from typing import Literal

from engines.risk.contracts import AmountComparison, Evidence, RiskFinding, RiskSummary

RiskLevel = Literal["high", "medium", "low", "none"]
ComparisonStatus = Literal["matched", "out_of_range", "reference_unavailable", "manual_review"]


def validate_evidence(evidence: Evidence | None) -> bool:
    """校验证据是否具备审计所需的全部内容。"""
    if evidence is None:
        return False
    return bool(
        evidence.attachment_id
        and evidence.page_or_location.strip()
        and evidence.original_text.strip()
        and evidence.field_name.strip()
        and evidence.rule_version.strip()
        and evidence.analyzed_at.tzinfo is not None
    )


def evaluate_amount(amount: Decimal, evidence: Evidence | None) -> RiskFinding:
    """检查金额阈值；没有完整证据时只能人工确认。"""
    if not validate_evidence(evidence):
        return RiskFinding(
            rule_code="amount.threshold",
            level="medium",
            status="manual_review",
            message="金额证据不足",
        )
    level: Literal["high", "low"] = "high" if amount >= Decimal("10000") else "low"
    return RiskFinding(
        rule_code="amount.threshold",
        level=level,
        status="matched",
        message="金额规则已执行",
        evidence=evidence,
    )


def evaluate_supplier(supplier_name: str, evidence: Evidence | None) -> RiskFinding:
    """供应商风险只提供辅助结论，不改变审批状态。"""
    if not validate_evidence(evidence):
        return RiskFinding(
            rule_code="supplier.screening",
            level="medium",
            status="manual_review",
            message="供应商证据不足",
        )
    level: Literal["medium", "low"] = "medium" if "异常" in supplier_name else "low"
    return RiskFinding(
        rule_code="supplier.screening",
        level=level,
        status="matched",
        message="供应商筛查已完成",
        evidence=evidence,
    )


def evaluate_rules(
    amount: Decimal, supplier_name: str, evidence: Evidence | None
) -> list[RiskFinding]:
    """按固定顺序运行一期规则，返回可审计风险项。"""
    return [evaluate_amount(amount, evidence), evaluate_supplier(supplier_name, evidence)]


def aggregate_risk_level(findings: Iterable[RiskFinding]) -> RiskSummary:
    """只汇总已确认且有证据的风险，人工项单独提示。"""
    confirmed = [
        item for item in findings if item.status == "confirmed" and validate_evidence(item.evidence)
    ]
    manual_required = any(item.status == "manual_review" for item in findings)
    levels = {item.level for item in confirmed}
    level: RiskLevel
    if "high" in levels:
        level = "high"
    elif "medium" in levels:
        level = "medium"
    elif "low" in levels:
        level = "low"
    else:
        level = "none"
    return RiskSummary(level=level, manual_review_required=manual_required)


def compare_amount(
    actual_amount: Decimal,
    currency: str,
    reference_min: Decimal | None,
    reference_max: Decimal | None,
    rule_version: str,
    source: str | None = None,
) -> AmountComparison:
    """进行同币种金额比对；缺少参考区间时不自行推断。"""
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("currency 必须是三位币种代码")
    if reference_min is None or reference_max is None:
        return AmountComparison(
            actual_amount=actual_amount,
            currency=currency.upper(),
            status="reference_unavailable",
            rule_version=rule_version,
            source=source,
        )
    difference = (
        actual_amount - reference_max
        if actual_amount > reference_max
        else actual_amount - reference_min
    )
    baseline = reference_max if actual_amount > reference_max else reference_min
    ratio = difference / baseline if baseline else None
    status: ComparisonStatus = (
        "matched" if reference_min <= actual_amount <= reference_max else "out_of_range"
    )
    return AmountComparison(
        actual_amount=actual_amount,
        currency=currency.upper(),
        reference_min=reference_min,
        reference_max=reference_max,
        difference=difference,
        ratio=ratio,
        status=status,
        rule_version=rule_version,
        source=source,
    )
