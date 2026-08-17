"""数据对象文档中的 21 张非核心业务表。

这些表使用显式 SQLAlchemy ``Table`` 定义，而不是把业务字段塞进一个
``payload`` JSON。这样迁移、查询和权限过滤都能直接依赖稳定的关系模型。
"""

from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)

from app.models.base import Base


def _id_column() -> Column[Any]:
    """创建由应用层生成 UUID 的主键列。"""
    return Column("id", Uuid, primary_key=True, default=uuid4)


def _created_at() -> Column[Any]:
    """创建带 UTC 默认值的创建时间列。"""
    return Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())


def _updated_at() -> Column[Any]:
    """创建带 UTC 默认值和更新触发行为的更新时间列。"""
    return Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


EXTENDED_TABLE_NAMES = (
    "users",
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
    "approval_instances",
    "approval_workflow_nodes",
    "document_status_logs",
    "analysis_tasks",
    "risk_findings",
    "market_price_references",
    "supplier_profiles",
    "manual_reviews",
    "audit_logs",
)


users = Table(
    "users",
    Base.metadata,
    _id_column(),
    Column("username", String(64), nullable=False, unique=True),
    Column("display_name", String(128), nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("organization_id", Uuid, nullable=False),
    Column("department_id", Uuid),
    Column("job_title", String(128)),
    Column("status", String(32), nullable=False, server_default="active"),
    Column("permission_version", Integer, nullable=False, server_default="1"),
    _created_at(),
    _updated_at(),
    CheckConstraint("status IN ('active', 'disabled')", name="ck_users_status"),
    CheckConstraint("permission_version >= 1", name="ck_users_permission_version_positive"),
)

roles = Table(
    "roles",
    Base.metadata,
    _id_column(),
    Column("role_code", String(32), nullable=False, unique=True),
    Column("role_name", String(64), nullable=False),
    Column("status", String(32), nullable=False, server_default="active"),
    _created_at(),
    _updated_at(),
    CheckConstraint("status IN ('active', 'disabled')", name="ck_roles_status"),
)

permissions = Table(
    "permissions",
    Base.metadata,
    _id_column(),
    Column("permission_code", String(128), nullable=False, unique=True),
    Column("permission_name", String(128), nullable=False),
    Column("resource_type", String(64), nullable=False),
    Column("action_type", String(32), nullable=False),
    _created_at(),
    _updated_at(),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    _id_column(),
    Column("user_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("role_id", Uuid, ForeignKey("roles.id"), nullable=False),
    Column("org_scope_json", JSON, nullable=False, default=dict),
    _created_at(),
    UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    _id_column(),
    Column("role_id", Uuid, ForeignKey("roles.id"), nullable=False),
    Column("permission_id", Uuid, ForeignKey("permissions.id"), nullable=False),
    _created_at(),
    UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
)

review_sessions = Table(
    "review_sessions",
    Base.metadata,
    _id_column(),
    Column("user_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("document_id", Uuid, ForeignKey("financial_documents.id")),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id")),
    Column("document_type", String(32)),
    Column("document_no", String(64)),
    Column("session_status", String(32), nullable=False, server_default="collecting"),
    Column("slot_state_json", JSON, nullable=False, default=dict),
    Column("state_version", Integer, nullable=False, server_default="1"),
    _created_at(),
    _updated_at(),
    CheckConstraint("state_version >= 1", name="ck_review_sessions_state_version_positive"),
)

session_messages = Table(
    "session_messages",
    Base.metadata,
    _id_column(),
    Column("session_id", Uuid, ForeignKey("review_sessions.id"), nullable=False),
    Column("role", String(16), nullable=False),
    Column("content", Text, nullable=False),
    Column("message_type", String(32), nullable=False),
    Column("metadata_json", JSON, nullable=False, default=dict),
    _created_at(),
)

document_line_items = Table(
    "document_line_items",
    Base.metadata,
    _id_column(),
    Column("document_id", Uuid, ForeignKey("financial_documents.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("item_type", String(32), nullable=False),
    Column("item_name", String(255), nullable=False),
    Column("expense_date", Date),
    Column("expense_location", String(255)),
    Column("quantity", Numeric(18, 4)),
    Column("unit_price", Numeric(18, 2)),
    Column("amount", Numeric(18, 2), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("remark", Text),
    Column("line_no", Integer, nullable=False),
    CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_line_items_quantity_nonnegative"),
    CheckConstraint(
        "unit_price IS NULL OR unit_price >= 0", name="ck_line_items_unit_price_nonnegative"
    ),
    CheckConstraint("amount >= 0", name="ck_line_items_amount_nonnegative"),
    UniqueConstraint("document_version_id", "line_no", name="uq_line_items_version_line_no"),
)

document_attachments = Table(
    "document_attachments",
    Base.metadata,
    _id_column(),
    Column("document_id", Uuid, ForeignKey("financial_documents.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("file_name", String(255), nullable=False),
    Column("file_type", String(16), nullable=False),
    Column("file_size", BigInteger, nullable=False),
    Column("file_path", String(1024), nullable=False),
    # 兼容旧版适配器命名，值与 FileStorage 对象键一致。
    Column("object_key", String(1024)),
    Column("file_hash", String(64), nullable=False),
    Column("storage_status", String(32), nullable=False, server_default="uploading"),
    Column("virus_scan_status", String(32), nullable=False, server_default="pending"),
    Column("virus_scan_version", String(64)),
    Column("virus_scanned_at", DateTime(timezone=True)),
    Column("parse_status", String(32), nullable=False, server_default="pending"),
    _created_at(),
    CheckConstraint("file_size > 0", name="ck_document_attachments_file_size_positive"),
    UniqueConstraint(
        "document_version_id", "file_hash", name="uq_document_attachments_version_hash"
    ),
)

attachment_parse_results = Table(
    "attachment_parse_results",
    Base.metadata,
    _id_column(),
    Column("attachment_id", Uuid, ForeignKey("document_attachments.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("document_category", String(32), nullable=False),
    Column("full_text", Text, nullable=False),
    Column("fields_json", JSON, nullable=False, default=dict),
    Column("evidence_positions_json", JSON, nullable=False, default=dict),
    Column("confidence", Numeric(5, 4)),
    Column("provider_name", String(128), nullable=False),
    Column("provider_version", String(64), nullable=False),
    _created_at(),
    CheckConstraint(
        "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
        name="ck_parse_confidence_range",
    ),
)

invoice_records = Table(
    "invoice_records",
    Base.metadata,
    _id_column(),
    Column("attachment_id", Uuid, ForeignKey("document_attachments.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("invoice_code", String(64)),
    Column("invoice_no", String(64)),
    Column("seller_name", String(255)),
    Column("buyer_name", String(255)),
    Column("invoice_date", Date),
    Column("amount_excluding_tax", Numeric(18, 2)),
    Column("tax_amount", Numeric(18, 2)),
    Column("amount_including_tax", Numeric(18, 2)),
    Column("currency", String(3)),
    CheckConstraint(
        "amount_excluding_tax IS NULL OR amount_excluding_tax >= 0",
        name="ck_invoice_amount_excluding_nonnegative",
    ),
    CheckConstraint("tax_amount IS NULL OR tax_amount >= 0", name="ck_invoice_tax_nonnegative"),
    CheckConstraint(
        "amount_including_tax IS NULL OR amount_including_tax >= 0",
        name="ck_invoice_amount_including_nonnegative",
    ),
)

approval_workflows = Table(
    "approval_workflows",
    Base.metadata,
    _id_column(),
    Column("workflow_name", String(128), nullable=False),
    Column("document_type", String(32), nullable=False),
    Column("workflow_code", String(64)),
    Column("workflow_version", Integer),
    Column("published", Boolean),
    Column("match_conditions_json", JSON, nullable=False, default=dict),
    Column("approval_mode", String(32), nullable=False, server_default="sequential"),
    Column("status", String(32), nullable=False, server_default="draft"),
    Column("version_no", Integer, nullable=False, server_default="1"),
    _created_at(),
    _updated_at(),
    CheckConstraint("approval_mode = 'sequential'", name="ck_approval_workflows_sequential"),
    CheckConstraint("version_no >= 1", name="ck_approval_workflows_version_positive"),
)

approval_workflow_nodes = Table(
    "approval_workflow_nodes",
    Base.metadata,
    _id_column(),
    Column("workflow_id", Uuid, ForeignKey("approval_workflows.id"), nullable=False),
    Column("node_name", String(128), nullable=False),
    Column("node_order", Integer, nullable=False),
    Column("approver_role", String(32), nullable=False),
    Column("approver_scope_json", JSON, nullable=False, default=dict),
    Column("primary_approver_id", Uuid, ForeignKey("users.id")),
    Column("approval_mode", String(32), nullable=False, server_default="sequential"),
    _created_at(),
    UniqueConstraint("workflow_id", "node_order", name="uq_workflow_nodes_workflow_order"),
    CheckConstraint("node_order >= 1", name="ck_workflow_nodes_order_positive"),
    CheckConstraint("approval_mode = 'sequential'", name="ck_workflow_nodes_sequential"),
)

approval_instances = Table(
    "approval_instances",
    Base.metadata,
    _id_column(),
    Column("workflow_id", Uuid, ForeignKey("approval_workflows.id"), nullable=False),
    Column("workflow_version_no", Integer, nullable=False),
    Column("document_id", Uuid, ForeignKey("financial_documents.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("instance_status", String(32), nullable=False, server_default="pending"),
    Column("current_node_id", Uuid, ForeignKey("approval_workflow_nodes.id")),
    Column("started_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("finished_at", DateTime(timezone=True)),
    CheckConstraint(
        "workflow_version_no >= 1", name="ck_approval_instances_workflow_version_positive"
    ),
)

document_status_logs = Table(
    "document_status_logs",
    Base.metadata,
    _id_column(),
    Column("document_id", Uuid, ForeignKey("financial_documents.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("from_status", String(32)),
    Column("to_status", String(32), nullable=False),
    Column("operator_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("remark", Text),
    _created_at(),
)

analysis_tasks = Table(
    "analysis_tasks",
    Base.metadata,
    _id_column(),
    Column("session_id", Uuid, ForeignKey("review_sessions.id")),
    Column("document_id", Uuid, ForeignKey("financial_documents.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("task_status", String(32), nullable=False, server_default="queued"),
    Column("current_step", String(64)),
    Column("rule_version", String(64), nullable=False),
    Column("model_metadata_json", JSON, nullable=False, default=dict),
    Column("retry_count", Integer, nullable=False, server_default="0"),
    Column("idempotency_key", String(128), nullable=False, unique=True),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("error_message", Text),
    CheckConstraint("retry_count >= 0", name="ck_analysis_tasks_retry_count_nonnegative"),
)

risk_findings = Table(
    "risk_findings",
    Base.metadata,
    _id_column(),
    Column("task_id", Uuid, ForeignKey("analysis_tasks.id"), nullable=False),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("risk_type", String(64), nullable=False),
    Column("risk_level", String(16), nullable=False),
    Column("risk_title", String(255), nullable=False),
    Column("description", Text),
    Column("actual_value_json", JSON, nullable=False, default=dict),
    Column("reference_value_json", JSON, nullable=False, default=dict),
    Column("threshold_json", JSON, nullable=False, default=dict),
    Column("evidence_json", JSON, nullable=False, default=dict),
    Column("rule_version", String(64), nullable=False),
    Column("model_metadata_json", JSON, nullable=False, default=dict),
    Column("suggestion_text", Text),
    Column("review_status", String(16), nullable=False, server_default="pending"),
    # 新代码以 review_status 为规范字段，保留旧版 finding_status 兼容读取。
    Column("finding_status", String(32)),
    _created_at(),
)

market_price_references = Table(
    "market_price_references",
    Base.metadata,
    _id_column(),
    Column("item_name", String(255), nullable=False),
    Column("specification", String(255)),
    Column("region", String(128)),
    Column("price_min", Numeric(18, 2), nullable=False),
    Column("price_max", Numeric(18, 2), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("source_name", String(255), nullable=False),
    Column("effective_date", Date, nullable=False),
    Column("expire_date", Date),
    Column("status", String(16), nullable=False, server_default="active"),
    _created_at(),
    _updated_at(),
    CheckConstraint("price_min >= 0", name="ck_market_price_min_nonnegative"),
    CheckConstraint("price_max >= price_min", name="ck_market_price_range"),
)

supplier_profiles = Table(
    "supplier_profiles",
    Base.metadata,
    _id_column(),
    Column("supplier_code", String(64), nullable=False, unique=True),
    Column("supplier_name", String(255), nullable=False),
    Column("credit_status", String(32)),
    Column("blacklist_status", String(16), nullable=False, server_default="normal"),
    Column("risk_tags_json", JSON, nullable=False, default=dict),
    Column("bank_accounts_json", JSON, nullable=False, default=dict),
    Column("historical_risk_json", JSON, nullable=False, default=dict),
    _updated_at(),
)

manual_reviews = Table(
    "manual_reviews",
    Base.metadata,
    _id_column(),
    Column("report_id", Uuid, ForeignKey("review_reports.id"), nullable=False),
    Column("risk_finding_id", Uuid, ForeignKey("risk_findings.id")),
    Column("document_version_id", Uuid, ForeignKey("document_versions.id"), nullable=False),
    Column("reviewer_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("review_result", String(32), nullable=False),
    Column("review_status", String(32)),
    Column("review_comment", Text),
    Column("reviewed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

audit_logs = Table(
    "audit_logs",
    Base.metadata,
    _id_column(),
    Column("user_id", Uuid, ForeignKey("users.id")),
    Column("actor_id", Uuid, ForeignKey("users.id")),
    Column("action_type", String(64), nullable=False),
    Column("action", String(128)),
    Column("resource_type", String(64), nullable=False),
    Column("resource_id", Uuid),
    Column("detail_json", JSON, nullable=False, default=dict),
    Column("ip_address", String(64)),
    _created_at(),
)


# 高频权限、版本、审批和风险查询使用显式索引，避免由 JSON 扩展字段承担筛选。
Index(
    "ix_financial_documents_applicant_status_updated",
    "financial_documents",
    "applicant_id",
    "document_status",
    "updated_at",
)
Index(
    "ix_document_attachments_version_parse_status",
    document_attachments.c.document_version_id,
    document_attachments.c.parse_status,
)
Index(
    "ix_risk_findings_version_level_status",
    risk_findings.c.document_version_id,
    risk_findings.c.risk_level,
    risk_findings.c.review_status,
)
Index(
    "ix_approval_tasks_approver_status_created",
    "approval_tasks",
    "approver_id",
    "task_status",
    "created_at",
)
Index(
    "ix_audit_logs_resource_created",
    audit_logs.c.resource_type,
    audit_logs.c.resource_id,
    audit_logs.c.created_at,
)
