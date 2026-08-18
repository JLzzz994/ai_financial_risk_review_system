"""PostgreSQL 风险事实与人工复核服务。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.sql_risk_repository import SqlRiskRepository
from app.schemas.risk import RiskEvaluationInput
from engines.risk.contracts import Evidence, RiskFinding
from engines.risk.rule_engine import evaluate_ten_rules


class PersistentRiskService:
    """执行确定性风险规则并追加版本化风险事实。"""

    def __init__(self, repository: SqlRiskRepository | None = None) -> None:
        """注入风险仓储。"""
        self.repository = repository or SqlRiskRepository()

    async def evaluate(
        self,
        session: AsyncSession,
        document_version_id: UUID,
        data: RiskEvaluationInput,
    ) -> list[RiskFinding]:
        """执行十类规则，所有结果绑定最近分析任务和不可变版本。"""
        task_id = await self.repository.latest_task_id(session, document_version_id)
        if task_id is None:
            raise ValueError("风险分析必须先创建分析任务")
        findings = evaluate_ten_rules(data.to_context())
        async with session.begin():
            await self.repository.append_findings(
                session,
                task_id,
                document_version_id,
                findings,
                settings.rag_rule_version,
            )
        return findings

    async def list_findings(
        self, session: AsyncSession, document_version_id: UUID
    ) -> list[RiskFinding]:
        """查询版本的全部风险事实，历史结果不覆盖。"""
        return await self.repository.list_by_version(session, document_version_id)

    async def list_findings_by_document(
        self, session: AsyncSession, document_id: UUID
    ) -> list[RiskFinding]:
        """查询单据所有版本的风险项。"""
        return await self.repository.list_by_document(session, document_id)

    async def get_version_id(self, session: AsyncSession, finding_id: UUID) -> UUID:
        """返回风险项所属版本，不存在时抛出业务错误。"""
        value = await self.repository.get_version_id(session, finding_id)
        if value is None:
            raise ValueError("风险项不存在")
        return value

    async def review(
        self,
        session: AsyncSession,
        finding_id: UUID,
        status: str,
        evidence: Evidence | None = None,
    ) -> RiskFinding:
        """保存人工复核状态；不改变审批状态。"""
        if status not in {"confirmed", "dismissed"}:
            raise ValueError("人工复核状态必须为 confirmed 或 dismissed")
        async with session.begin():
            return await self.repository.update_review_status(
                session, finding_id, status, evidence
            )


__all__ = ["PersistentRiskService"]
