from decimal import Decimal
from uuid import uuid4

from app.services.reconciliation_report_service import (
    FindingReportItem,
    ReconciliationReportService,
)
from engines.model.contracts import RagEvidence
from engines.risk.contracts import Evidence
from engines.risk.reconciliation_engine import (
    ReconciliationContext,
    evaluate_reconciliation_rules,
)


def test_report_keeps_rule_fact_and_policy_evidence_separate() -> None:
    evidence = Evidence(
        attachment_id=uuid4(),
        page_or_location="sheet1!A2:H2",
        original_text="ERP-001 平台结算 1180",
        field_name="platform_settlement_amount",
        confidence=Decimal("0.97"),
        rule_version="reconciliation-v1",
    )
    findings = evaluate_reconciliation_rules(
        ReconciliationContext(
            platform="tmall",
            shop_name="demo",
            order_no="ERP-001",
            expected_receivable=Decimal("1280"),
            platform_settlement_amount=Decimal("1180"),
            actual_received_amount=None,
            remittance_due=True,
            settlement_count=2,
            settlement_subject="主体A",
            payment_subject="主体A",
            parse_confidence=Decimal("0.97"),
            evidence=evidence,
        )
    )
    target = next(
        item
        for item in findings
        if item.rule_code == "reconciliation.settlement_amount_difference"
    )
    policy = RagEvidence(
        chunk_id="rule-1",
        content="存在结算差异时应核对调整项并人工复核。",
        source_title="平台结算规则",
        score=0.95,
        rule_version="2026-09",
        page_or_location="3.1",
    )

    report = ReconciliationReportService().render(
        document_version_id=uuid4(),
        platform="tmall",
        shop_name="demo",
        order_no="ERP-001",
        items=[FindingReportItem(target, (policy,))],
    )

    assert "风险等级：`high`" in report
    assert "平台结算规则" in report
    assert "风险等级和命中状态来自确定性规则" in report
    assert "待模型服务生成；不得覆盖上述规则事实" in report
