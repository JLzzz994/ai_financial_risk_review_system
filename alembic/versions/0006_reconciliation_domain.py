"""新增慧经营电商对账领域表。"""

from alembic import op

revision = "0006_reconciliation_domain"
down_revision = "0005_parse_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """模型统一由 Base.metadata 注册，复用项目现有显式建表策略。"""
    from app.models import Base
    from app.models import reconciliation as _reconciliation  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """按外键依赖逆序删除本次领域表。"""
    for table_name in (
        "reconciliation_remittances",
        "reconciliation_adjustments",
        "reconciliation_refunds",
        "reconciliation_settlements",
        "reconciliation_orders",
        "reconciliation_cases",
    ):
        op.drop_table(table_name)
