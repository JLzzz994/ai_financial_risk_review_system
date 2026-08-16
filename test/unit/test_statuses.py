"""状态单一来源的单元测试。"""

from decimal import Decimal

from engines.common.statuses import ApprovalDecision, ApprovalTaskStatus, DocumentStatus
from engines.common.types import Money


def test_status_values_are_lower_snake_case() -> None:
    """验证持久化状态只使用文档约定的小写值。"""
    assert DocumentStatus.PENDING_REVIEW.value == "pending_review"
    assert ApprovalTaskStatus.PENDING.value == "pending"
    assert ApprovalDecision.APPROVE.value == "approve"


def test_money_preserves_decimal_precision() -> None:
    """验证金额类型基于 Decimal 而非浮点数。"""
    amount = Money(Decimal("100.01"))
    assert isinstance(amount, Decimal)
    assert amount == Decimal("100.01")
