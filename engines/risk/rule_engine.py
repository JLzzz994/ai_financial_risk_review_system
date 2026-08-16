"""确定性风险规则执行器。"""

from decimal import Decimal

from engines.risk.contracts import Evidence, RiskFinding


def evaluate_amount(amount: Decimal, evidence: Evidence | None) -> RiskFinding:
    """检查金额阈值；没有完整证据时只能人工确认。"""
    if evidence is None:
        return RiskFinding(rule_code="amount.threshold", level="medium", status="manual_review", message="金额证据不足")
    level = "high" if amount >= Decimal("10000") else "low"
    return RiskFinding(rule_code="amount.threshold", level=level, status="matched", message="金额规则已执行", evidence=evidence)


def evaluate_supplier(supplier_name: str, evidence: Evidence | None) -> RiskFinding:
    """供应商风险只提供辅助结论，不改变审批状态。"""
    if evidence is None:
        return RiskFinding(rule_code="supplier.screening", level="medium", status="manual_review", message="供应商证据不足")
    level = "medium" if "异常" in supplier_name else "low"
    return RiskFinding(rule_code="supplier.screening", level=level, status="matched", message="供应商筛查已完成", evidence=evidence)
