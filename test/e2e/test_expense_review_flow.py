"""费用报销样板链路端到端验收。"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.schemas.approval import ApprovalDecisionCommand, DecisionCode
from app.schemas.documents import CreateDocumentCommand
from app.schemas.risk import RiskEvaluationInput
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.document_service import DocumentService
from app.services.report_service import ReportService
from app.services.risk_service import RiskService
from engines.risk.contracts import Evidence


def test_expense_review_sample_flow() -> None:
    """验证费用报销从草稿到审批和报告的核心链路。"""
    applicant = uuid4()
    document_service = DocumentService()
    document = document_service.create_draft(CreateDocumentCommand(applicant_id=applicant, applicant_department="财务", total_amount=Decimal("12000.00"), apply_date=date.today(), reason_text="差旅"))
    version = document_service.submit(document.document_id, applicant, 1)

    evidence = Evidence(attachment_id=uuid4(), page_or_location="page-1", original_text="住宿费 12000", field_name="total_amount", confidence=Decimal("0.98"), rule_version="v1")
    risk = RiskService().evaluate(version.document_id, RiskEvaluationInput(amount=Decimal("12000"), supplier_name="正常供应商", evidence=evidence))
    assert risk.findings[0].evidence is not None

    approver = uuid4()
    approval = ApprovalService()
    task_id = uuid4()
    approval.assign(task_id, approver, is_last_node=True)
    decision = approval.submit_decision(task_id, ApprovalDecisionCommand(approver_id=approver, decision=DecisionCode.APPROVE, comment="人工确认通过", idempotency_key="expense-1"))
    assert decision.document_status == "approved"
    report = ReportService().finalize_report(version.version_id, "费用报销风险审核报告")
    assert report.document_version_id == version.version_id
    audit = AuditService().record(approver, "approval_decision", "approval_task", task_id)
    assert audit.action == "approval_decision"
