"""数据对象文档中非核心表的最小 SQLAlchemy 元数据。"""

from sqlalchemy import JSON, Column, DateTime, Table, Uuid, func

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
    "approval_workflows", "document_status_logs", "analysis_tasks", "risk_findings", "market_price_references",
    "supplier_profiles", "manual_reviews", "audit_logs",
)

for _table_name in EXTENDED_TABLE_NAMES:
    Table(_table_name, Base.metadata, *_common_columns(), extend_existing=True)
