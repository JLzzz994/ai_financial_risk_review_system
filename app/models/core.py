"""核心财务单据、版本、审批任务和风险报告模型。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class FinancialDocument(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """财务单据公共对象，金额始终使用 Decimal 保持精度。"""

    __tablename__ = "financial_documents"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_financial_documents_total_amount_nonnegative"),
        CheckConstraint("current_version >= 0", name="ck_financial_documents_current_version_nonnegative"),
    )

    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    document_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    applicant_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    applicant_department: Mapped[str] = mapped_column(String(128), nullable=False)
    budget_department: Mapped[str | None] = mapped_column(String(128))
    payee_name: Mapped[str | None] = mapped_column(String(255))
    payee_account: Mapped[str | None] = mapped_column(String(128))
    expense_category: Mapped[str | None] = mapped_column(String(64))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    apply_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    document_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    document_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    document_state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document")


class DocumentVersion(UuidPrimaryKeyMixin, Base):
    """不可变的单据提交快照，所有审核产物都应绑定此版本。"""

    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_no", name="uq_document_versions_document_version"),)

    document_id: Mapped[UUID] = mapped_column(ForeignKey("financial_documents.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    document_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    document: Mapped[FinancialDocument] = relationship(back_populates="versions")


class ApprovalTask(UuidPrimaryKeyMixin, Base):
    """顺序审批中的单节点任务，最终决定由审批人提交。"""

    __tablename__ = "approval_tasks"

    instance_id: Mapped[UUID] = mapped_column(ForeignKey("approval_instances.id"), nullable=False)
    node_id: Mapped[UUID] = mapped_column(ForeignKey("approval_workflow_nodes.id"), nullable=False)
    approver_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    decision: Mapped[str | None] = mapped_column(String(16))
    review_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column()


class ReviewReport(UuidPrimaryKeyMixin, Base):
    """绑定单据版本的风险审核报告，历史报告不覆盖。"""

    __tablename__ = "review_reports"

    document_id: Mapped[UUID] = mapped_column(ForeignKey("financial_documents.id"), nullable=False)
    document_version_id: Mapped[UUID] = mapped_column(ForeignKey("document_versions.id"), nullable=False)
    report_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    overall_risk_level: Mapped[str | None] = mapped_column(String(16))
    report_content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    generated_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)
