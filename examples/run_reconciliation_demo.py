"""离线演示：异常订单 -> 确定性规则 -> 制度证据 -> Markdown 报告。

该脚本不伪造 OCR、Milvus、Reranker 或 LLM 在线调用；它使用 examples 下的结构化
案例和制度证据夹具，展示生产链路中规则事实与 AI/RAG 证据的职责边界。
"""

import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from app.schemas.reconciliation import ReconciliationEvaluationInput
from app.services.reconciliation_report_service import (
    FindingReportItem,
    ReconciliationReportService,
)
from app.services.reconciliation_service import ReconciliationService
from engines.model.contracts import RagEvidence
from engines.risk.contracts import Evidence

ROOT = Path(__file__).resolve().parent


def _load_json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def main() -> None:
    case = _load_json("reconciliation_case.json")
    policy_map = _load_json("policy_evidence.json")
    version_id = uuid4()

    case["evidence"] = Evidence(
        document_version_id=version_id,
        attachment_id=uuid4(),
        page_or_location="平台账单.xlsx / sheet1 / row 2",
        original_text=(
            "ERP-20260901-0001, settlement=1180.00, settlement_count=2, "
            "remittance=null"
        ),
        field_name="platform_settlement_amount",
        confidence=Decimal("0.97"),
        rule_version="reconciliation-v1",
    )

    response = ReconciliationService().evaluate(
        version_id,
        ReconciliationEvaluationInput.model_validate(case),
    )

    items: list[FindingReportItem] = []
    for finding in response.findings:
        policy = tuple(
            RagEvidence(**item) for item in policy_map.get(finding.rule_code, [])
        )
        items.append(FindingReportItem(finding=finding, policy_evidence=policy))

    report = ReconciliationReportService().render(
        document_version_id=version_id,
        platform=case["platform"],
        shop_name=case["shop_name"],
        order_no=case["order_no"],
        items=items,
    )

    output = ROOT / "reconciliation_demo_report.md"
    output.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n报告已写入: {output}")


if __name__ == "__main__":
    main()
