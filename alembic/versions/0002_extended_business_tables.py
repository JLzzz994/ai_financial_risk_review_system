"""补齐数据对象文档中的业务表。"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_extended_business_tables"
down_revision = "0001_core_tables"
branch_labels = None
depends_on = None

TABLES = (
    "roles",
    "permissions",
    "user_roles",
    "role_permissions",
    "review_sessions",
    "session_messages",
    "document_line_items",
    "document_attachments",
    "attachment_parse_results",
    "invoice_records",
    "approval_workflows",
    "document_status_logs",
    "analysis_tasks",
    "risk_findings",
    "market_price_references",
    "supplier_profiles",
    "manual_reviews",
    "audit_logs",
)


def upgrade() -> None:
    """创建扩展业务表的通用元数据列。"""
    uuid = postgresql.UUID(as_uuid=True)
    for table_name in TABLES:
        op.create_table(
            table_name,
            sa.Column("id", uuid, primary_key=True),
            sa.Column(
                "payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )


def downgrade() -> None:
    """按创建顺序反向删除扩展表。"""
    for table_name in reversed(TABLES):
        op.drop_table(table_name)
