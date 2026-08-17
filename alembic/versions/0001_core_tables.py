"""创建任务 2 的核心单据、版本、审批任务和报告表。"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_core_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建核心表及其精度、版本唯一性约束。"""
    uuid = postgresql.UUID(as_uuid=True)
    json_type = postgresql.JSONB(astext_type=sa.Text())
    # 核心表引用的主数据表先建立最小占位主键，后续任务会补齐其字段。
    op.create_table("users", sa.Column("id", uuid, primary_key=True))
    op.create_table("approval_instances", sa.Column("id", uuid, primary_key=True))
    op.create_table("approval_workflow_nodes", sa.Column("id", uuid, primary_key=True))
    op.create_table(
        "financial_documents",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("document_type", sa.String(32), nullable=False),
        sa.Column("document_no", sa.String(64), nullable=False),
        sa.Column("applicant_id", uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("applicant_department", sa.String(128), nullable=False),
        sa.Column("budget_department", sa.String(128)),
        sa.Column("payee_name", sa.String(255)),
        sa.Column("payee_account", sa.String(128)),
        sa.Column("expense_category", sa.String(64)),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("apply_date", sa.Date, nullable=False),
        sa.Column("reason_text", sa.Text, nullable=False),
        sa.Column(
            "document_payload", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("document_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("current_version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("document_state_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "total_amount >= 0", name="ck_financial_documents_total_amount_nonnegative"
        ),
        sa.CheckConstraint(
            "current_version >= 0", name="ck_financial_documents_current_version_nonnegative"
        ),
    )
    op.create_index("ix_financial_documents_document_no", "financial_documents", ["document_no"])
    op.create_table(
        "document_versions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("document_id", uuid, sa.ForeignKey("financial_documents.id"), nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("document_snapshot_json", json_type, nullable=False),
        sa.Column("created_by", uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "document_id", "version_no", name="uq_document_versions_document_version"
        ),
    )
    op.create_table(
        "approval_tasks",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("instance_id", uuid, sa.ForeignKey("approval_instances.id"), nullable=False),
        sa.Column("node_id", uuid, sa.ForeignKey("approval_workflow_nodes.id"), nullable=False),
        sa.Column("approver_id", uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("decision", sa.String(16)),
        sa.Column("review_comment", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "review_reports",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("document_id", uuid, sa.ForeignKey("financial_documents.id"), nullable=False),
        sa.Column(
            "document_version_id", uuid, sa.ForeignKey("document_versions.id"), nullable=False
        ),
        sa.Column("report_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("overall_risk_level", sa.String(16)),
        sa.Column(
            "report_content", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    """按外键依赖反向删除任务 2 创建的表。"""
    op.drop_table("review_reports")
    op.drop_table("approval_tasks")
    op.drop_table("document_versions")
    op.drop_index("ix_financial_documents_document_no", table_name="financial_documents")
    op.drop_table("financial_documents")
    op.drop_table("approval_workflow_nodes")
    op.drop_table("approval_instances")
    op.drop_table("users")
