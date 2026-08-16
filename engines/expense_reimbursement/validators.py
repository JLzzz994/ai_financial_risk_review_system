"""费用报销领域校验。"""

from decimal import Decimal


def validate_expense_amount(amount: Decimal) -> Decimal:
    """验证金额为正且最多两位小数。"""
    if amount <= 0 or amount.as_tuple().exponent < -2:
        raise ValueError("报销金额必须为正且最多两位小数")
    return amount
