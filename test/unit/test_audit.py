"""审计事件测试。"""

from uuid import uuid4

from app.services.audit_service import AuditService


def test_audit_event_is_appended() -> None:
    """审计事件保存动作和资源标识。"""
    event = AuditService().record(uuid4(), "approval_decision", "approval_task", uuid4())
    assert event.action == "approval_decision"
