"""持久化附件解析重试事实和幂等键。"""

import sqlalchemy as sa

from alembic import context, op

revision = "0005_parse_idempotency"
down_revision = "0004_explicit_data_object_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为已重建的附件表增加可恢复、可幂等的事实字段。"""
    # 0004 的 Base.metadata.create_all 已包含这些字段；离线模式无法读取
    # Inspector，因此生成 PostgreSQL 幂等 DDL，兼容已存在或尚未存在的字段。
    if context.is_offline_mode():
        op.execute(
            "ALTER TABLE document_attachments "
            "ADD COLUMN IF NOT EXISTS parse_retry_count INTEGER NOT NULL DEFAULT 0"
        )
        op.execute(
            "ALTER TABLE document_attachments "
            "ADD COLUMN IF NOT EXISTS parse_error TEXT"
        )
        op.execute(
            "ALTER TABLE document_attachments "
            "ADD COLUMN IF NOT EXISTS parse_idempotency_key VARCHAR(128)"
        )
        op.execute(
            "ALTER TABLE attachment_parse_results "
            "ADD COLUMN IF NOT EXISTS parse_idempotency_key VARCHAR(128)"
        )
        op.execute(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
            "WHERE conname = 'uq_attachment_parse_results_idempotency') THEN "
            "ALTER TABLE attachment_parse_results ADD CONSTRAINT "
            "uq_attachment_parse_results_idempotency UNIQUE "
            "(attachment_id, document_version_id, parse_idempotency_key); "
            "END IF; END $$"
        )
        return
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    attachment_columns = {
        column["name"] for column in inspector.get_columns("document_attachments")
    }
    result_columns = {
        column["name"] for column in inspector.get_columns("attachment_parse_results")
    }
    if "parse_retry_count" not in attachment_columns:
        op.add_column(
            "document_attachments",
            sa.Column("parse_retry_count", sa.Integer(), nullable=False, server_default="0"),
        )
    if "parse_error" not in attachment_columns:
        op.add_column("document_attachments", sa.Column("parse_error", sa.Text(), nullable=True))
    if "parse_idempotency_key" not in attachment_columns:
        op.add_column(
            "document_attachments",
            sa.Column("parse_idempotency_key", sa.String(128), nullable=True),
        )
    if "parse_idempotency_key" not in result_columns:
        op.add_column(
            "attachment_parse_results",
            sa.Column("parse_idempotency_key", sa.String(128), nullable=True),
        )
    constraints = {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints("attachment_parse_results")
    }
    if "uq_attachment_parse_results_idempotency" not in constraints:
        op.create_unique_constraint(
            "uq_attachment_parse_results_idempotency",
            "attachment_parse_results",
            ["attachment_id", "document_version_id", "parse_idempotency_key"],
        )


def downgrade() -> None:
    """回滚附件解析幂等字段。"""
    if context.is_offline_mode():
        op.execute(
            "ALTER TABLE attachment_parse_results "
            "DROP CONSTRAINT IF EXISTS uq_attachment_parse_results_idempotency"
        )
        op.execute(
            "ALTER TABLE attachment_parse_results "
            "DROP COLUMN IF EXISTS parse_idempotency_key"
        )
        op.execute(
            "ALTER TABLE document_attachments DROP COLUMN IF EXISTS parse_idempotency_key"
        )
        op.execute("ALTER TABLE document_attachments DROP COLUMN IF EXISTS parse_error")
        op.execute(
            "ALTER TABLE document_attachments DROP COLUMN IF EXISTS parse_retry_count"
        )
        return
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints("attachment_parse_results")
    }
    if "uq_attachment_parse_results_idempotency" in constraints:
        op.drop_constraint(
            "uq_attachment_parse_results_idempotency", "attachment_parse_results", type_="unique"
        )
    for table, column in (
        ("attachment_parse_results", "parse_idempotency_key"),
        ("document_attachments", "parse_idempotency_key"),
        ("document_attachments", "parse_error"),
        ("document_attachments", "parse_retry_count"),
    ):
        if column in {item["name"] for item in inspector.get_columns(table)}:
            op.drop_column(table, column)
