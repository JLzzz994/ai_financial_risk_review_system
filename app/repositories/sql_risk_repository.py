"""PostgreSQL 风险项仓储。"""

import json
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import DocumentVersion
from app.models.extended import analysis_tasks, risk_findings
from engines.risk.contracts import Evidence, RiskFinding


class SqlRiskRepository:
    """追加风险事实、查询版本风险和保存人工复核状态。"""

    async def latest_task_id(
        self, session: AsyncSession, document_version_id: UUID
    ) -> UUID | None:
        """取得版本最近一次分析任务，风险项必须绑定该任务。"""
        result = await session.execute(
            select(analysis_tasks.c.id)
            .where(analysis_tasks.c.document_version_id == document_version_id)
            .order_by(analysis_tasks.c.started_at.desc())
            .limit(1)
        )
        value = result.scalar_one_or_none()
        return UUID(str(value)) if value is not None else None

    async def append_findings(
        self,
        session: AsyncSession,
        task_id: UUID,
        document_version_id: UUID,
        findings: list[RiskFinding],
        rule_version: str,
    ) -> list[RiskFinding]:
        """追加一批风险事实，历史记录不可覆盖。"""
        for finding in findings:
            review_status = (
                finding.status
                if finding.status in {"confirmed", "dismissed", "manual_review"}
                else "pending"
            )
            evidence = finding.evidence.model_dump(mode="json") if finding.evidence else {}
            await session.execute(
                insert(risk_findings).values(
                    id=uuid4(),
                    task_id=task_id,
                    document_version_id=document_version_id,
                    risk_type=finding.rule_code,
                    risk_level=finding.level,
                    risk_title=finding.message[:255],
                    description=finding.message,
                    actual_value_json=self._json_value(finding.actual_value),
                    reference_value_json=self._json_value(finding.reference_value),
                    threshold_json=self._json_value(finding.threshold),
                    evidence_json=evidence,
                    rule_version=rule_version,
                    model_metadata_json={},
                    suggestion_text=finding.suggestion,
                    review_status=review_status,
                    finding_status=finding.status,
                )
            )
        return findings

    async def list_by_version(
        self, session: AsyncSession, document_version_id: UUID
    ) -> list[RiskFinding]:
        """按不可变版本查询风险项和证据。"""
        result = await session.execute(
            select(risk_findings)
            .where(risk_findings.c.document_version_id == document_version_id)
            .order_by(risk_findings.c.created_at, risk_findings.c.id)
        )
        return [self._to_finding(row) for row in result.mappings().all()]

    async def list_by_document(
        self, session: AsyncSession, document_id: UUID
    ) -> list[RiskFinding]:
        """按单据查询所有版本的风险项，供工作台和风险页使用。"""
        result = await session.execute(
            select(risk_findings)
            .join(DocumentVersion, risk_findings.c.document_version_id == DocumentVersion.id)
            .where(DocumentVersion.document_id == document_id)
            .order_by(risk_findings.c.created_at, risk_findings.c.id)
        )
        return [self._to_finding(row) for row in result.mappings().all()]

    async def get_version_id(
        self, session: AsyncSession, finding_id: UUID
    ) -> UUID | None:
        """取得风险项所属版本，路由据此校验数据范围。"""
        result = await session.execute(
            select(risk_findings.c.document_version_id).where(risk_findings.c.id == finding_id)
        )
        value = result.scalar_one_or_none()
        return UUID(str(value)) if value is not None else None

    async def update_review_status(
        self,
        session: AsyncSession,
        finding_id: UUID,
        status: str,
        evidence: Evidence | None = None,
    ) -> RiskFinding:
        """只更新风险复核字段，不更新单据或审批状态。"""
        values: dict[str, Any] = {"review_status": status, "finding_status": status}
        if evidence is not None:
            values["evidence_json"] = self._json_value(evidence.model_dump(mode="json"))
        await session.execute(
            update(risk_findings).where(risk_findings.c.id == finding_id).values(**values)
        )
        result = await session.execute(
            select(risk_findings).where(risk_findings.c.id == finding_id)
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("风险项不存在")
        return self._to_finding(row)

    @staticmethod
    def _to_finding(row: Any) -> RiskFinding:
        """将数据库风险事实转换为领域模型。"""
        evidence_data = row.get("evidence_json") or None
        evidence = Evidence.model_validate(evidence_data) if evidence_data else None
        raw_status = str(row.get("finding_status") or row.get("review_status") or "pending")
        if raw_status not in {"pending", "matched", "confirmed", "dismissed", "manual_review"}:
            raw_status = "pending"
        level = cast(Literal["high", "medium", "low", "none"], str(row["risk_level"]))
        status = cast(
            Literal["pending", "matched", "confirmed", "dismissed", "manual_review"],
            raw_status,
        )
        return RiskFinding(
            rule_code=str(row["risk_type"]),
            level=level,
            status=status,
            message=str(row.get("description") or row["risk_title"]),
            evidence=evidence,
            actual_value=dict(row.get("actual_value_json") or {}),
            reference_value=dict(row.get("reference_value_json") or {}),
            threshold=dict(row.get("threshold_json") or {}),
            suggestion=row.get("suggestion_text"),
        )

    @staticmethod
    def _json_value(value: Any) -> Any:
        """把 Decimal、UUID 等领域值转换为 JSONB 可保存的值。"""
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))


__all__ = ["SqlRiskRepository"]
