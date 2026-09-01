"""对账审核报告渲染。

报告正文只汇总已经存在的规则事实、制度证据和人工处理状态，不重新判断风险。
"""

from dataclasses import dataclass
from uuid import UUID

from engines.model.contracts import RagEvidence
from engines.risk.contracts import RiskFinding


@dataclass(frozen=True, slots=True)
class FindingReportItem:
    finding: RiskFinding
    policy_evidence: tuple[RagEvidence, ...] = ()
    ai_explanation: str | None = None


class ReconciliationReportService:
    """生成面试演示和生产报告都可复用的 Markdown 快照。"""

    def render(
        self,
        *,
        document_version_id: UUID,
        platform: str,
        shop_name: str,
        order_no: str,
        items: list[FindingReportItem],
    ) -> str:
        high = sum(item.finding.level == "high" for item in items)
        medium = sum(item.finding.level == "medium" for item in items)
        manual = sum(item.finding.status == "manual_review" for item in items)

        lines = [
            "# 慧策·慧经营对账异常审核报告",
            "",
            f"- 审核版本：`{document_version_id}`",
            f"- 平台：{platform}",
            f"- 店铺：{shop_name}",
            f"- ERP 订单号：{order_no}",
            f"- 高风险项：{high}",
            f"- 中风险项：{medium}",
            f"- 待人工复核：{manual}",
            "",
            "> 风险等级和命中状态来自确定性规则；RAG/LLM 仅补充制度依据和处理建议。",
            "",
        ]

        for index, item in enumerate(items, start=1):
            finding = item.finding
            lines.extend(
                [
                    f"## {index}. {finding.rule_code}",
                    "",
                    f"- 风险等级：`{finding.level}`",
                    f"- 状态：`{finding.status}`",
                    f"- 规则事实：{finding.message}",
                    f"- 实际值：`{finding.actual_value}`",
                    f"- 参考值：`{finding.reference_value}`",
                ]
            )
            if finding.evidence is not None:
                lines.extend(
                    [
                        f"- 原始证据位置：{finding.evidence.page_or_location}",
                        f"- 解析置信度：{finding.evidence.confidence}",
                    ]
                )
            if item.policy_evidence:
                lines.append("- 制度依据：")
                for evidence in item.policy_evidence:
                    location = (
                        f"，{evidence.page_or_location}" if evidence.page_or_location else ""
                    )
                    lines.append(
                        f"  - {evidence.source_title}{location}：{evidence.content}"
                    )
            else:
                lines.append("- 制度依据：未检索到，建议人工核对最新平台规则/财务制度")
            if item.ai_explanation:
                lines.append(f"- AI 解释与建议：{item.ai_explanation}")
            elif finding.level != "low":
                lines.append("- AI 解释与建议：待模型服务生成；不得覆盖上述规则事实")
            lines.append("")

        return "\n".join(lines).strip() + "\n"


__all__ = ["FindingReportItem", "ReconciliationReportService"]
