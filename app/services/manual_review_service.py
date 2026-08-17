"""人工复核用例服务。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from engines.risk.contracts import Evidence, RiskFinding


class ManualReviewRecord:
    """不可覆盖的人工复核记录。"""

    def __init__(self, document_version_id: UUID, finding: RiskFinding) -> None:
        self.review_id = uuid4()
        self.document_version_id = document_version_id
        self.finding = finding
        self.status = "pending"
        self.created_at = datetime.now(UTC)
        self.reviewer_id: UUID | None = None
        self.comment: str | None = None


class ManualReviewService:
    """提供人工复核入口，不允许 AI 代替审核人员确认。"""

    def __init__(self) -> None:
        self._records: dict[UUID, ManualReviewRecord] = {}

    def create(self, document_version_id: UUID, finding: RiskFinding) -> ManualReviewRecord:
        """为证据不足的风险项创建复核记录。"""
        if finding.status != "manual_review":
            raise ValueError("只有 manual_review 风险项可以创建人工复核")
        record = ManualReviewRecord(document_version_id, finding)
        self._records[record.review_id] = record
        return record

    def update_review_status(
        self,
        review_id: UUID,
        reviewer_id: UUID,
        status: str,
        comment: str,
        evidence: Evidence | None = None,
    ) -> ManualReviewRecord:
        """保存审核人员决定；每次调用都要求处理意见。"""
        if not comment.strip():
            raise ValueError("人工复核必须填写处理意见")
        if status not in {"confirmed", "dismissed"}:
            raise ValueError("人工复核状态必须为 confirmed 或 dismissed")
        if review_id not in self._records:
            raise ValueError("人工复核记录不存在")
        record = self._records[review_id]
        record.status = status
        record.reviewer_id = reviewer_id
        record.comment = comment
        if evidence is not None:
            record.finding.evidence = evidence
        return record
