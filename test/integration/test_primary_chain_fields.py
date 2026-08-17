"""主链路字段契约测试。"""

from app.models import Base


def test_primary_chain_fields_are_explicit() -> None:
    """权限、附件、风险、审批和审计关键字段不能只存在 payload。"""
    assert "object_key" in Base.metadata.tables["document_attachments"].c
    assert "finding_status" in Base.metadata.tables["risk_findings"].c
    assert "review_status" in Base.metadata.tables["manual_reviews"].c
    assert "action" in Base.metadata.tables["audit_logs"].c
