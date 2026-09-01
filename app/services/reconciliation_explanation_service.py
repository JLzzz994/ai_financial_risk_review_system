"""对账风险解释编排。

规则引擎拥有风险事实最终解释权；RAG/LLM 只能补充制度依据和处理建议。
"""

from dataclasses import dataclass

from app.services.rag_service import RagService
from engines.model.contracts import RagEvidence
from engines.risk.contracts import RiskFinding


@dataclass(frozen=True, slots=True)
class ReconciliationExplanation:
    rule_code: str
    risk_message: str
    policy_evidence: tuple[RagEvidence, ...]
    explanation_prompt: str


class ReconciliationExplanationService:
    """为已产生的规则事实检索制度依据，并构造受约束的 LLM 输入。"""

    def __init__(self, rag_service: RagService) -> None:
        self.rag_service = rag_service

    async def prepare(
        self,
        finding: RiskFinding,
        *,
        platform: str,
        shop_name: str,
        top_k: int = 5,
    ) -> ReconciliationExplanation:
        query = (
            f"{platform} 平台 {finding.rule_code} 对账规则、结算规则、退款规则、"
            "财务处理制度和人工复核要求"
        )
        evidence = await self.rag_service.retrieve(
            query,
            top_k,
            item_name=finding.rule_code,
        )
        sources = "\n".join(
            f"[{index}] {item.source_title}: {item.content}"
            for index, item in enumerate(evidence, start=1)
        )
        prompt = (
            "你是电商财务对账审核助手。以下规则结果是确定性系统事实，禁止修改风险"
            "等级、命中状态、金额差异或审批状态。只能根据给定制度证据解释原因并给出"
            "处理建议；证据不足时明确建议人工复核，不得自行补充制度。\n\n"
            f"平台: {platform}\n店铺: {shop_name}\n"
            f"规则: {finding.rule_code}\n规则事实: {finding.message}\n"
            f"实际值: {finding.actual_value}\n参考值: {finding.reference_value}\n\n"
            f"制度证据:\n{sources or '无'}"
        )
        return ReconciliationExplanation(
            rule_code=finding.rule_code,
            risk_message=finding.message,
            policy_evidence=tuple(evidence),
            explanation_prompt=prompt,
        )


__all__ = ["ReconciliationExplanation", "ReconciliationExplanationService"]
