from decimal import Decimal
from uuid import uuid4

import pytest

from engines.reconciliation.parse_contracts import ParsedField, ParsedReconciliationRow
from engines.tasks.reconciliation_tasks import (
    ReconciliationStage,
    build_reconciliation_task_plan,
    run_reconciliation_task,
)


def test_parsed_row_uses_minimum_field_confidence() -> None:
    row = ParsedReconciliationRow(
        platform="tmall",
        shop_name="旗舰店",
        order_no="ORDER-001",
        expected_receivable=Decimal("1000"),
        settlement_amount=Decimal("990"),
        source_kind="ocr",
        fields=[
            ParsedField(
                name="order_no",
                value="ORDER-001",
                page_or_location="page=1,bbox=1,1,10,10",
                original_text="ORDER-001",
                confidence=Decimal("0.98"),
            ),
            ParsedField(
                name="settlement_amount",
                value="990",
                page_or_location="page=1,bbox=20,1,30,10",
                original_text="990.00",
                confidence=Decimal("0.72"),
            ),
        ],
    )
    assert row.minimum_confidence == Decimal("0.72")
    assert row.missing_key_fields() == []


def test_pipeline_keeps_rules_before_rag_and_llm() -> None:
    plan = build_reconciliation_task_plan(uuid4(), "idem-001")
    assert plan.stages.index(ReconciliationStage.RULE_EVALUATING) < plan.stages.index(
        ReconciliationStage.POLICY_RETRIEVING
    )
    assert plan.stages.index(ReconciliationStage.POLICY_RETRIEVING) < plan.stages.index(
        ReconciliationStage.EXPLAINING
    )


def test_worker_does_not_fake_success_when_not_configured() -> None:
    with pytest.raises(RuntimeError, match="Worker 尚未配置"):
        run_reconciliation_task(uuid4(), "idem-002")


def test_fourth_attempt_moves_to_manual_review() -> None:
    plan = run_reconciliation_task(uuid4(), "idem-003", attempt=4)
    assert plan.stages == (ReconciliationStage.MANUAL_REVIEW,)
