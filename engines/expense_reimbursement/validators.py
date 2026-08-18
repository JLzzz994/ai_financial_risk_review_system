"""费用报销领域校验。"""

from collections.abc import Sequence
from decimal import Decimal

from engines.expense_reimbursement.contracts import ExpenseLine


def validate_expense_amount(amount: Decimal) -> Decimal:
    """验证金额为正且最多两位小数。"""
    exponent = amount.as_tuple().exponent
    if amount <= 0 or not isinstance(exponent, int) or exponent < -2:
        raise ValueError("报销金额必须为正且最多两位小数")
    return amount


def validate_expense_lines(lines: Sequence[ExpenseLine], currency: str = "CNY") -> Decimal:
    """校验明细非空、币种一致并返回精确到两位的明细合计。"""
    normalized_currency = currency.strip().upper()
    if len(normalized_currency) != 3 or not normalized_currency.isalpha():
        raise ValueError("费用报销币种必须是三位大写字母")
    if not lines:
        raise ValueError("费用报销至少需要一条明细")

    total = Decimal("0.00")
    for line in lines:
        if not line.expense_item.strip():
            raise ValueError("费用明细名称不能为空")
        if line.currency.strip().upper() != normalized_currency:
            raise ValueError("同一费用报销单的明细币种必须一致")
        total += validate_expense_amount(line.amount)
    return total.quantize(Decimal("0.01"))


def validate_expense_total(
    total_amount: Decimal,
    lines: Sequence[ExpenseLine],
    currency: str = "CNY",
) -> Decimal:
    """校验单据总额与明细合计一致，并返回规范化总额。"""
    normalized_total = validate_expense_amount(total_amount).quantize(Decimal("0.01"))
    line_total = validate_expense_lines(lines, currency)
    if normalized_total != line_total:
        raise ValueError("单据总额必须与明细合计一致")
    return normalized_total
