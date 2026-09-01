"""慧经营对账审核 Worker 编排。

生产链路严格按：装配上下文 -> 规则 -> 风险落库 -> RAG -> LLM 解释 -> 报告。
LLM 只处理已存在的 RiskFinding，不参与金额差异、重复结算等确定性判断。
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.sql_reconciliation_repository import SqlReconciliationRepository
from app.repositories.sql_risk_repository import SqlRiskRepository
from app.services.reconciliation_explanation_service import ReconciliationExplanationService
from app.services.reconciliation_report_service import ReconciliationReportService
from engines.model.explanation_contracts import ExplanationAdapter, ExplanationRequest
from engines.risk.contracts import RiskFinding
from engines.risk.reconciliation_engine import evaluate_reconciliation_rules

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReconciliationWorkerResult:
    document_version_id: UUID
    order_no: str
    finding_count: int
    explained_count: int
    report_markdown: str


ProgressCallback = Callable[[str, int], Awaitable[None]]


class ReconciliationWorker:
    """可注入、可测试的生产对账分析编排器。"""

    def __init__(
        self,
        *,
        repository: SqlReconciliationRepository,
        risk_repository: SqlRiskRepository,
        explanation_service: ReconciliationExplanationService,
        explanation_adapter: ExplanationAdapter,
        report_service: ReconciliationReportService,
        rule_version: str = "reconciliation-v1",
    ) -> None:
        self.repository = repository
        self.risk_repository = risk_repository
        self.explanation_service = explanation_service
        self.explanation_adapter = explanation_adapter
        self.report_service = report_service
        self.rule_version = rule_version

    async def run(
        self,
        session: AsyncSession,
        *,
        task_id: UUID,
        document_version_id: UUID,
        order_no: str,
        progress: ProgressCallback,
    ) -> ReconciliationWorkerResult:
        await progress("normalizing", 20)
        context = await self.repository.load_context(
            session,
            document_version_id=document_version_id,
            order_no=order_no,
        )

        await progress("rule_evaluating", 40)
        findings = evaluate_reconciliation_rules(context)
        async with session.begin():
            await self.risk_repository.append_findings(
                session,
                task_id,
                document_version_id,
                findings,
                self.rule_version,
            )

        explained: list[tuple[RiskFinding, str, str, tuple[object, ...]]] = []
        actionable = [item for item in findings if item.level in {"high", "medium"}]
        for index, finding in enumerate(actionable, start=1):
            await progress(
                "policy_retrieving",
                45 + min(20, int(index / max(len(actionable), 1) * 20)),
            )
            prepared = await self.explanation_service.prepare(
                finding,
                platform=context.platform,
                shop_name=context.shop_name,
            )
            await progress("explaining", 70)
            result = await self.explanation_adapter.explain(
                ExplanationRequest(
                    prompt=prepared.explanation_prompt,
                    rule_code=finding.rule_code,
                    risk_level=finding.level,
                    finding_status=finding.status,
                )
            )
            explained.append(
                (finding, result.explanation, result.suggestion, prepared.policy_evidence)
            )

        await progress("aggregating", 90)
        report_markdown = self.report_service.build_markdown(
            platform=context.platform,
            shop_name=context.shop_name,
            order_no=context.order_no,
            findings=findings,
            explanations=explained,
        )
        await progress("succeeded", 100)
        logger.info(
            "reconciliation_worker_succeeded",
            extra={
                "task_id": str(task_id),
                "document_version_id": str(document_version_id),
                "order_no": order_no,
                "finding_count": len(findings),
            },
        )
        return ReconciliationWorkerResult(
            document_version_id=document_version_id,
            order_no=order_no,
            finding_count=len(findings),
            explained_count=len(explained),
            report_markdown=report_markdown,
        )


__all__ = ["ReconciliationWorker", "ReconciliationWorkerResult"]
