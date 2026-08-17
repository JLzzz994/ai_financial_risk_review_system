"""以显式关系模型重建开发数据库的 25 张业务表。

0001-0003 是早期占位迁移，扩展表使用了 ``payload``。根据已审核的数据
对象文档，开发库允许不兼容重建，因此本迁移不修改旧脚本，而是从当前
版本开始删除旧表并按 ``Base.metadata`` 创建完整字段、外键和索引。
"""

from alembic import op
from app.models import Base

revision = "0004_explicit_data_object_tables"
down_revision = "0003_primary_chain_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """删除占位表并创建数据对象文档规定的完整关系模型。"""
    bind = op.get_bind()
    # 开发数据库明确允许重建，不保留旧 payload 表中的不兼容数据。
    Base.metadata.drop_all(bind=bind, checkfirst=True)
    Base.metadata.create_all(bind=bind, checkfirst=False)


def downgrade() -> None:
    """回退到空数据库基线；再次 upgrade 可重新创建完整模型。"""
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
