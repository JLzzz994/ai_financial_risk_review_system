"""补齐主链路表的显式业务字段。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_primary_chain_fields"
down_revision = "0002_extended_business_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为权限、附件、审批、风险、复核和审计表增加显式字段。"""
    uuid = postgresql.UUID(as_uuid=True)
    additions = {
        "roles": [("role_code", sa.String(64)), ("role_name", sa.String(128))],
        "permissions": [("permission_code", sa.String(128)), ("permission_name", sa.String(128))],
        "review_sessions": [("document_version_id", uuid), ("session_status", sa.String(32))],
        "document_attachments": [("document_version_id", uuid), ("object_key", sa.String(512)), ("parse_status", sa.String(32))],
        "approval_workflows": [("workflow_code", sa.String(64)), ("workflow_version", sa.Integer), ("published", sa.Boolean)],
        "approval_instances": [("document_version_id", uuid), ("workflow_id", uuid), ("instance_status", sa.String(32))],
        "risk_findings": [("document_version_id", uuid), ("rule_code", sa.String(128)), ("risk_level", sa.String(16)), ("finding_status", sa.String(32)), ("evidence_json", postgresql.JSONB)],
        "manual_reviews": [("risk_finding_id", uuid), ("reviewer_id", uuid), ("review_status", sa.String(32)), ("review_comment", sa.Text)],
        "audit_logs": [("actor_id", uuid), ("action", sa.String(128)), ("resource_type", sa.String(64)), ("resource_id", uuid)],
    }
    for table_name, columns in additions.items():
        for column_name, column_type in columns:
            op.add_column(table_name, sa.Column(column_name, column_type, nullable=True))


def downgrade() -> None:
    """删除本迁移增加的显式字段。"""
    additions = {
        "roles": ["role_code", "role_name"],
        "permissions": ["permission_code", "permission_name"],
        "review_sessions": ["document_version_id", "session_status"],
        "document_attachments": ["document_version_id", "object_key", "parse_status"],
        "approval_workflows": ["workflow_code", "workflow_version", "published"],
        "approval_instances": ["document_version_id", "workflow_id", "instance_status"],
        "risk_findings": ["document_version_id", "rule_code", "risk_level", "finding_status", "evidence_json"],
        "manual_reviews": ["risk_finding_id", "reviewer_id", "review_status", "review_comment"],
        "audit_logs": ["actor_id", "action", "resource_type", "resource_id"],
    }
    for table_name, columns in additions.items():
        for column_name in reversed(columns):
            op.drop_column(table_name, column_name)
