"""费用报销单内存仓储，后续替换为 SQLAlchemy 实现。"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from engines.document_types.contracts import DocumentType
from engines.expense_reimbursement.contracts import ExpenseLine


@dataclass
class StoredDocument:
    """仓储内部单据对象。"""

    document_id: UUID
    document_no: str
    applicant_id: UUID
    applicant_department: str
    total_amount: Decimal
    currency: str
    apply_date: date
    reason_text: str
    status: str = "draft"
    current_version: int = 0
    state_version: int = 1
    line_items: tuple[ExpenseLine, ...] = ()
    document_type: str = DocumentType.EXPENSE_REIMBURSEMENT.value


@dataclass(frozen=True)
class StoredVersion:
    """不可变版本记录。"""

    version_id: UUID
    document_id: UUID
    version_no: int
    created_by: UUID
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class InMemoryDocumentRepository:
    """测试和开发阶段使用的单据仓储。"""

    def __init__(self) -> None:
        """初始化空仓储。"""
        self.documents: dict[UUID, StoredDocument] = {}
        self.versions: list[StoredVersion] = []
        self._sequences: dict[DocumentType, int] = {}

    def next_document_no(self, document_type: DocumentType) -> str:
        """按单据类型生成仅供内存兼容服务使用的递增编号。"""
        self._sequences[document_type] = self._sequences.get(document_type, 0) + 1
        prefix = {
            DocumentType.PUBLIC_PAYMENT: "PUB",
            DocumentType.PREPAYMENT: "PRE",
            DocumentType.BATCH_PAYMENT: "BAT",
            DocumentType.EXPENSE_REIMBURSEMENT: "EXP",
            DocumentType.TRAVEL_REIMBURSEMENT: "TRV",
        }[document_type]
        return f"{prefix}-{self._sequences[document_type]:08d}"

    def add_version(self, document: StoredDocument, actor_id: UUID) -> StoredVersion:
        """创建并追加不可变版本。"""
        version = StoredVersion(uuid4(), document.document_id, document.current_version, actor_id)
        self.versions.append(version)
        return version
