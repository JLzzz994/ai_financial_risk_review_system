"""财务审核领域的 SQLAlchemy 数据模型。"""

from app.models.base import Base

# 先注册外键依赖表，再加载引用 users/approval_instances 的 ORM 模型。
from app.models.core import ApprovalTask, DocumentVersion, FinancialDocument, ReviewReport
from app.models.extended import EXTENDED_TABLE_NAMES
from app.models.reconciliation import RECONCILIATION_TABLE_NAMES

__all__ = [
    "ApprovalTask",
    "Base",
    "DocumentVersion",
    "FinancialDocument",
    "ReviewReport",
    "EXTENDED_TABLE_NAMES",
    "RECONCILIATION_TABLE_NAMES",
]
