"""数据对象文档中非核心表的最小 SQLAlchemy 元数据。"""

from sqlalchemy import BOOLEAN, JSON, Column, DateTime, Integer, String, Table, Text, Uuid, func

from app.models.base import Base

def _common_columns() -> list[Column[object]]:
    """为每张扩展表创建独立的公共列对象。"""
    return [
        Column("id", Uuid, primary_key=True),
        Column("payload", JSON, nullable=False, server_default="{}"),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ]

EXTENDED_TABLE_NAMES = (
    "roles", "permissions", "user_roles", "role_permissions", "review_sessions", "session_messages",
    "document_line_items", "document_attachments", "attachment_parse_results", "invoice_records",
    "approval_workflows", "approval_instances", "approval_workflow_nodes", "document_status_logs", "analysis_tasks", "risk_findings", "market_price_references",
    "supplier_profiles", "manual_reviews", "audit_logs",
)

for _table_name in EXTENDED_TABLE_NAMES:
    Table(_table_name, Base.metadata, *_common_columns(), extend_existing=True)

# 主链路字段与数据对象文档保持同名；其余动态字段仍放在 payload。
_TABLE_FIELDS = {
    "roles": (("role_code", String(64)), ("role_name", String(128))),
    "permissions": (("permission_code", String(128)), ("permission_name", String(128))),
    "review_sessions": (("document_version_id", Uuid), ("session_status", String(32))),
    "document_attachments": (("document_version_id", Uuid), ("object_key", String(512)), ("parse_status", String(32))),
    "approval_workflows": (("workflow_code", String(64)), ("workflow_version", Integer), ("published", BOOLEAN)),
    "approval_instances": (("document_version_id", Uuid), ("workflow_id", Uuid), ("instance_status", String(32))),
    "risk_findings": (("document_version_id", Uuid), ("rule_code", String(128)), ("risk_level", String(16)), ("finding_status", String(32)), ("evidence_json", JSON)),
    "manual_reviews": (("risk_finding_id", Uuid), ("reviewer_id", Uuid), ("review_status", String(32)), ("review_comment", Text)),
    "audit_logs": (("actor_id", Uuid), ("action", String(128)), ("resource_type", String(64)), ("resource_id", Uuid)),
}

for _table_name, _fields in _TABLE_FIELDS.items():
    _table = Base.metadata.tables[_table_name]
    for _field_name, _field_type in _fields:
        if _field_name not in _table.c:
            _table.append_column(Column(_field_name, _field_type))
