"""费用报销领域输入模型。"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ExpenseLine:
    """费用报销明细的最小领域对象。"""

    expense_item: str
    amount: Decimal
    currency: str = "CNY"
