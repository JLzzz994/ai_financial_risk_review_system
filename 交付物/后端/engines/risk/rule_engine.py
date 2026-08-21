"""确定性风险规则执行器。

规则模块只生成风险事实，不接触审批状态，也不调用 LLM。
"""

from collections.abc import Iterable
from decimal import Decimal
from typing import Literal

from engines.risk.contracts import AmountComparison, Evidence, RiskContext, RiskFinding, RiskSummary

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


def evaluate_ten_rules(context: RiskContext) -> list[RiskFinding]:
    """按 PRD 固定顺序执行十类风险规则，缺输入或证据统一转人工复核。"""

    def finding(
        rule_code: str,
        message: str,
        *,
        level: Literal["high", "medium", "low"] = "low",
        actual: dict[str, object] | None = None,
        reference: dict[str, object] | None = None,
        threshold: dict[str, object] | None = None,
        missing: bool = False,
    ) -> RiskFinding:
        """创建带审计计算值的规则结果。"""
        if not validate_evidence(context.evidence) or missing:
            return RiskFinding(
                rule_code=rule_code,
                level="medium",
                status="manual_review",
                message=f"{message}，证据或结构化数据不足",
                evidence=context.evidence,
            )
        return RiskFinding(
            rule_code=rule_code,
            level=level,
            status="matched",
            message=message,
            evidence=context.evidence,
            actual_value=actual or {},
            reference_value=reference or {},
            threshold=threshold or {},
        )

    invoice_missing = context.invoice_total is None
    invoice_difference = (
        context.amount - context.invoice_total if context.invoice_total is not None else None
    )
    line_missing = context.line_item_total is None
    line_difference = (
        context.line_item_total - context.amount if context.line_item_total is not None else None
    )
    contract_missing = context.contract_amount is None or context.payment_amount is None
    batch_missing = context.batch_total is None or context.payment_count is None
    market_missing = (
        context.market_unit_price is None
        or context.market_price_min is None
        or context.market_price_max is None
    )
    return [
        finding(
            "document.invoice_amount_consistency",
            "单据与发票金额一致性检查完成",
            level="high" if invoice_difference not in (None, Decimal("0")) else "low",
            actual={"document_amount": context.amount, "invoice_total": context.invoice_total},
            reference={"difference": invoice_difference},
            missing=invoice_missing,
        ),
        finding(
            "line_items.total_consistency",
            "明细与总金额一致性检查完成",
            level="high" if line_difference not in (None, Decimal("0")) else "low",
            actual={"document_amount": context.amount, "line_item_total": context.line_item_total},
            reference={"difference": line_difference},
            missing=line_missing,
        ),
        finding(
            "contract.payment_consistency",
            "合同与付款一致性检查完成",
            level="high"
            if context.payment_amount is not None
            and context.contract_amount is not None
            and context.payment_amount > context.contract_amount
            else "low",
            actual={
                "contract_amount": context.contract_amount,
                "payment_amount": context.payment_amount,
            },
            missing=contract_missing,
        ),
        finding(
            "batch_payment.consistency",
            "批量付款一致性检查完成",
            level="high" if context.duplicate_account_count > 0 else "low",
            actual={
                "batch_total": context.batch_total,
                "payment_count": context.payment_count,
                "duplicate_account_count": context.duplicate_account_count,
            },
            missing=batch_missing,
        ),
        finding(
            "expense.standard_compliance",
            "费用标准合规性检查完成",
            level=(
                "high"
                if context.expense_limit is not None and context.amount > context.expense_limit
                else "low"
            ),
            actual={"amount": context.amount},
            reference={"expense_limit": context.expense_limit},
            missing=context.expense_limit is None,
        ),
        finding(
            "market_price.reasonableness",
            "市场价格合理性检查完成",
            level="high"
            if context.market_unit_price is not None
            and context.market_price_min is not None
            and context.market_price_max is not None
            and not context.market_price_min
            <= context.market_unit_price
            <= context.market_price_max
            else "low",
            actual={"unit_price": context.market_unit_price},
            reference={
                "price_min": context.market_price_min,
                "price_max": context.market_price_max,
            },
            missing=market_missing,
        ),
        finding(
            "behavior.anomaly",
            "消费行为异常检查完成",
            level="medium" if context.behavior_flags else "low",
            actual={"flags": context.behavior_flags},
        ),
        finding(
            "supplier.risk",
            "供应商风险检查完成",
            level="high" if context.supplier_risk_flags else "low",
            actual={"flags": context.supplier_risk_flags, "supplier_name": context.supplier_name},
        ),
        finding(
            "attachment.completeness",
            "附件完整性检查完成",
            level="high"
            if context.attachment_count < context.required_attachment_count
            or not context.attachment_fields_complete
            else "low",
            actual={
                "attachment_count": context.attachment_count,
                "fields_complete": context.attachment_fields_complete,
            },
            reference={"required_attachment_count": context.required_attachment_count},
        ),
        finding(
            "invoice.duplicate",
            "重复票据检查完成",
            level="high" if context.duplicate_invoice else "low",
            actual={"duplicate": context.duplicate_invoice},
        ),
    ]


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
