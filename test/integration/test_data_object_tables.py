"""数据对象文档与 SQLAlchemy 元数据的契约测试。"""

from sqlalchemy import Numeric, create_engine

from app.models import EXTENDED_TABLE_NAMES, Base


def test_extended_table_names_match_document_inventory() -> None:
    """扩展表覆盖数据对象文档中的 21 张非核心表。"""
    assert len(EXTENDED_TABLE_NAMES) == 21
    assert set(EXTENDED_TABLE_NAMES).issubset(Base.metadata.tables)


def test_data_object_inventory_has_exactly_twenty_five_tables() -> None:
    """模型基线必须只包含数据对象文档规定的 25 张业务表。"""
    expected = {
        "users",
        "roles",
        "permissions",
        "user_roles",
        "role_permissions",
        "review_sessions",
        "session_messages",
        "financial_documents",
        "document_versions",
        "document_line_items",
        "document_attachments",
        "attachment_parse_results",
        "invoice_records",
        "approval_workflows",
        "approval_workflow_nodes",
        "approval_instances",
        "approval_tasks",
        "document_status_logs",
        "analysis_tasks",
        "risk_findings",
        "review_reports",
        "market_price_references",
        "supplier_profiles",
        "manual_reviews",
        "audit_logs",
    }
    assert set(Base.metadata.tables) == expected


def test_version_binding_columns_and_amount_precision_are_explicit() -> None:
    """附件、解析、分析、风险、复核、审批和报告都必须绑定版本。"""
    for table_name in (
        "document_line_items",
        "document_attachments",
        "attachment_parse_results",
        "invoice_records",
        "analysis_tasks",
        "risk_findings",
        "review_reports",
        "manual_reviews",
    ):
        assert "document_version_id" in Base.metadata.tables[table_name].c

    for table_name, column_name in (
        ("financial_documents", "total_amount"),
        ("document_line_items", "unit_price"),
        ("document_line_items", "amount"),
        ("market_price_references", "price_min"),
        ("market_price_references", "price_max"),
    ):
        column_type = Base.metadata.tables[table_name].c[column_name].type
        assert isinstance(column_type, Numeric)
        assert (column_type.precision, column_type.scale) == (18, 2)


def test_core_relationship_foreign_keys_are_declared() -> None:
    """核心关系的外键不能由 payload 动态承载。"""
    assert "users.id" in {
        str(item.column)
        for item in Base.metadata.tables["financial_documents"].c.applicant_id.foreign_keys
    }
    assert "document_versions.id" in {
        str(item.column)
        for item in Base.metadata.tables["document_attachments"].c.document_version_id.foreign_keys
    }
    assert "analysis_tasks.id" in {
        str(item.column) for item in Base.metadata.tables["risk_findings"].c.task_id.foreign_keys
    }


def test_explicit_metadata_can_create_a_local_contract_database() -> None:
    """契约测试使用内存 SQLite 验证所有关系定义可被创建，不依赖真实 PostgreSQL。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    assert len(Base.metadata.tables) == 25
