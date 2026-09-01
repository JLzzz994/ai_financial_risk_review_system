"""电商多平台对账确定性风险规则。

规则只生成风险事实，不调用 LLM，也不修改审批状态。
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from engines.risk.contracts import Evidence, RiskFinding
from engines.risk.rule_engine import validate_evidence


class ReconciliationContext(BaseModel):
    """一次对账审核的结构化上下文。"""

    platform: str
    shop_name: str
    order_no: str
    settlement_no: str | None = None
    expected_receivable: Decimal
    platform_settlement_amount: Decimal | None = None
    refund_amount: Decimal = Decimal("0")
    adjustment_amount: Decimal = Decimal("0")
    actual_received_amount: Decimal | None = None
    settlement_count: int = Field(default=1, ge=0)
    refund_count: int = Field(default=0, ge=0)
    settlement_status: str | None = None
    refund_status: str | None = None
    payment_subject: str | None = None
    settlement_subject: str | None = None
    adjustment_reason_present: bool = True
    remittance_due: bool = False
    parsed_fields_complete: bool = True
    parse_confidence: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    evidence: Evidence | None = None
    tolerance: Decimal = Decimal("0.01")
    adjustment_threshold: Decimal = Decimal("1000")
    low_confidence_threshold: Decimal = Decimal("0.85")


def _finding(
    context: ReconciliationContext,
    rule_code: str,
    message: str,
    *,
    level: Literal["high", "medium", "low"] = "low",
    actual: dict[str, object] | None = None,
    reference: dict[str, object] | None = None,
    missing: bool = False,
) -> RiskFinding:
    if missing or not validate_evidence(context.evidence):
        return RiskFinding(
            rule_code=rule_code,
            level="medium",
            status="manual_review",
            message=f"{message}，证据或结构化数据不足",
            evidence=context.evidence,
            actual_value=actual or {},
            reference_value=reference or {},
        )
    return RiskFinding(
        rule_code=rule_code,
        level=level,
        status="matched",
        message=message,
        evidence=context.evidence,
        actual_value=actual or {},
        reference_value=reference or {},
    )


def evaluate_reconciliation_rules(context: ReconciliationContext) -> list[RiskFinding]:
    """按固定顺序执行电商对账异常规则。"""

    settlement_missing = context.platform_settlement_amount is None
    received_missing = context.actual_received_amount is None and context.remittance_due
    net_expected = context.expected_receivable - context.refund_amount + context.adjustment_amount
    settlement_diff = (
        None if context.platform_settlement_amount is None
        else context.platform_settlement_amount - net_expected
    )
    received_diff = (
        None if context.actual_received_amount is None
        else context.actual_received_amount - (
            context.platform_settlement_amount
            if context.platform_settlement_amount is not None
            else net_expected
        )
    )
    low_confidence = (
        context.parse_confidence is not None
        and context.parse_confidence < context.low_confidence_threshold
    )
    subject_mismatch = (
        bool(context.payment_subject)
        and bool(context.settlement_subject)
        and context.payment_subject != context.settlement_subject
    )

    return [
        _finding(
            context,
            "reconciliation.settlement_amount_difference",
            "订单应收与平台结算金额核验完成",
            level="high" if settlement_diff is not None and abs(settlement_diff) > context.tolerance else "low",
            actual={
                "expected_receivable": context.expected_receivable,
                "refund_amount": context.refund_amount,
                "adjustment_amount": context.adjustment_amount,
                "net_expected": net_expected,
                "platform_settlement_amount": context.platform_settlement_amount,
            },
            reference={"difference": settlement_diff, "tolerance": context.tolerance},
            missing=settlement_missing,
        ),
        _finding(
            context,
            "reconciliation.refund_anomaly",
            "退款记录核验完成",
            level="high" if (
                context.refund_amount > context.expected_receivable
                or context.refund_count > 1
                or (context.refund_amount > 0 and context.refund_status not in {"success", "completed", "refunded"})
            ) else "low",
            actual={
                "refund_amount": context.refund_amount,
                "refund_count": context.refund_count,
                "refund_status": context.refund_status,
                "order_amount": context.expected_receivable,
            },
        ),
        _finding(
            context,
            "reconciliation.duplicate_settlement",
            "重复结算核验完成",
            level="high" if context.settlement_count > 1 else "low",
            actual={
                "order_no": context.order_no,
                "settlement_no": context.settlement_no,
                "settlement_count": context.settlement_count,
            },
        ),
        _finding(
            context,
            "reconciliation.remittance_missing",
            "实际回款核验完成",
            level=(
                "high" if context.remittance_due and context.actual_received_amount is None
                else "high" if received_diff is not None and abs(received_diff) > context.tolerance
                else "low"
            ),
            actual={
                "actual_received_amount": context.actual_received_amount,
                "platform_settlement_amount": context.platform_settlement_amount,
                "remittance_due": context.remittance_due,
            },
            reference={"difference": received_diff, "tolerance": context.tolerance},
            missing=received_missing,
        ),
        _finding(
            context,
            "reconciliation.adjustment_anomaly",
            "金额调整核验完成",
            level="high" if (
                abs(context.adjustment_amount) > context.adjustment_threshold
                or (context.adjustment_amount != 0 and not context.adjustment_reason_present)
            ) else "low",
            actual={
                "adjustment_amount": context.adjustment_amount,
                "adjustment_reason_present": context.adjustment_reason_present,
            },
            reference={"threshold": context.adjustment_threshold},
        ),
        _finding(
            context,
            "reconciliation.subject_mismatch",
            "结算主体与回款主体核验完成",
            level="high" if subject_mismatch else "low",
            actual={
                "settlement_subject": context.settlement_subject,
                "payment_subject": context.payment_subject,
            },
            missing=context.settlement_subject is None or context.payment_subject is None,
        ),
        _finding(
            context,
            "reconciliation.parse_quality",
            "账单关键字段与解析置信度核验完成",
            level="medium" if low_confidence or not context.parsed_fields_complete else "low",
            actual={
                "parsed_fields_complete": context.parsed_fields_complete,
                "parse_confidence": context.parse_confidence,
            },
            reference={"low_confidence_threshold": context.low_confidence_threshold},
            missing=context.parse_confidence is None,
        ),
    ]


__all__ = ["ReconciliationContext", "evaluate_reconciliation_rules"]
