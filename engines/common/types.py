"""领域层类型别名，避免金额和置信度退化为不安全的 float。"""

from decimal import Decimal
from typing import NewType

Money = NewType("Money", Decimal)
Confidence = NewType("Confidence", Decimal)
