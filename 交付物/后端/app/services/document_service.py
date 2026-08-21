"""费用报销单用例服务。"""

from uuid import UUID, uuid4

from app.logging_config import get_logger, log_boundary
from app.repositories.document_repository import (
    InMemoryDocumentRepository,
    StoredDocument,
)
from app.schemas.documents import CreateDocumentCommand, DocumentResponse, DocumentVersionResponse
from engines.expense_reimbursement.contracts import ExpenseLine
from engines.expense_reimbursement.validators import validate_expense_total

logger = get_logger(__name__)


class DocumentService:
    """编排单据创建、提交和退回重提。"""

    def __init__(self, repository: InMemoryDocumentRepository | None = None) -> None:
        """注入仓储。"""
        self.repository = repository or InMemoryDocumentRepository()

    def create_draft(self, command: CreateDocumentCommand) -> DocumentResponse:
        """创建五类单据草稿并在内存兼容服务中回显实际类型。"""
        log_boundary(logger, "create_draft", "enter", applicant_id=str(command.applicant_id))
        try:
            if command.currency != "CNY":
                raise ValueError("MVP 仅支持 CNY")
            line_items = tuple(
                ExpenseLine(item.expense_item, item.amount, item.currency)
                for item in command.line_items
            )
            if line_items:
                validate_expense_total(command.total_amount, line_items, command.currency)
            document = StoredDocument(
                uuid4(),
                self.repository.next_document_no(command.document_type),
                command.applicant_id,
                command.applicant_department,
                command.total_amount,
                command.currency,
                command.apply_date,
                command.reason_text,
                line_items=line_items,
                document_type=command.document_type.value,
            )
            self.repository.documents[document.document_id] = document
            response = self._response(document)
        except Exception:
            logger.exception("document operation=create_draft status=failed")
            raise
        log_boundary(logger, "create_draft", "exit", document_id=str(response.document_id))
        return response

    def submit(
        self, document_id: UUID, actor_id: UUID, expected_state_version: int
    ) -> DocumentVersionResponse:
        """提交草稿并创建不可变版本，检查乐观锁。"""
        log_boundary(
            logger,
            "submit",
            "enter",
            document_id=str(document_id),
            actor_id=str(actor_id),
        )
        try:
            document = self._get(document_id)
            if document.state_version != expected_state_version:
                raise ValueError("单据已被其他请求修改")
            if document.status not in {"draft", "returned"}:
                raise ValueError("当前状态不可提交")
            document.current_version += 1
            document.state_version += 1
            document.status = "pending_review"
            version = self.repository.add_version(document, actor_id)
            response = DocumentVersionResponse(
                version_id=version.version_id,
                document_id=version.document_id,
                version_no=version.version_no,
                created_by=version.created_by,
            )
        except Exception:
            logger.exception("document operation=submit status=failed document_id=%s", document_id)
            raise
        log_boundary(
            logger, "submit", "exit", document_id=str(document_id), status="pending_review"
        )
        return response

    def resubmit_after_return(
        self, document_id: UUID, actor_id: UUID, expected_state_version: int
    ) -> DocumentVersionResponse:
        """退回重提从第一个审核节点重新开始，并保留旧版本。"""
        return self.submit(document_id, actor_id, expected_state_version)

    def get(self, document_id: UUID) -> DocumentResponse:
        """查询单据当前状态。"""
        return self._response(self._get(document_id))

    def list_versions(self, document_id: UUID) -> list[DocumentVersionResponse]:
        """查询单据的不可变版本列表。"""
        self._get(document_id)
        return [
            DocumentVersionResponse(
                version_id=item.version_id,
                document_id=item.document_id,
                version_no=item.version_no,
                created_by=item.created_by,
            )
            for item in self.repository.versions
            if item.document_id == document_id
        ]

    def _get(self, document_id: UUID) -> StoredDocument:
        """按 ID 获取单据，不存在时抛出统一业务错误。"""
        if document_id not in self.repository.documents:
            raise ValueError("单据不存在")
        return self.repository.documents[document_id]

    @staticmethod
    def _response(document: StoredDocument) -> DocumentResponse:
        """转换为 API 响应模型。"""
        return DocumentResponse(
            document_id=document.document_id,
            document_no=document.document_no,
            applicant_id=document.applicant_id,
            total_amount=document.total_amount,
            currency=document.currency,
            document_status=document.status,
            current_version=document.current_version,
            state_version=document.state_version,
            document_type=document.document_type,
        )
