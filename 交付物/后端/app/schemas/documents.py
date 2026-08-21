"""费用报销单 API 模型。"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from engines.document_types.contracts import DocumentType, DocumentTypePayload


class CreateDocumentCommand(BaseModel):
    """创建五类单据草稿并保留费用报销兼容字段。"""

    applicant_id: UUID
    applicant_department: str = Field(min_length=1, max_length=128)
    total_amount: Decimal = Field(ge=Decimal("0.01"), max_digits=18, decimal_places=2)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    apply_date: date
    reason_text: str = Field(min_length=1, max_length=2000)
    line_items: list["DocumentLineItemCommand"] = Field(default_factory=list)
    document_type: DocumentType = DocumentType.EXPENSE_REIMBURSEMENT
    document_payload: DocumentTypePayload | None = None

    @model_validator(mode="after")
    def validate_payload_type(self) -> "CreateDocumentCommand":
        """确保专属 payload 的类型与命令单据类型一致。"""
        if (
            self.document_payload is not None
            and self.document_payload.document_type != self.document_type
        ):
            raise ValueError("单据类型与专属载荷类型不一致")
        return self


class DocumentLineItemCommand(BaseModel):
    """费用报销草稿中的一条明细。"""

    expense_item: str = Field(min_length=1, max_length=255)
    expense_date: date
    amount: Decimal = Field(gt=Decimal("0"), max_digits=18, decimal_places=2)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    invoice_no: str | None = Field(default=None, max_length=64)
    remark: str | None = Field(default=None, max_length=2000)


class DocumentResponse(BaseModel):
    """单据响应模型。"""

    document_id: UUID
    document_no: str
    applicant_id: UUID
    total_amount: Decimal
    currency: str
    document_status: str
    current_version: int
    state_version: int
    document_type: str = "expense_reimbursement"
    applicant_department: str | None = None
    budget_department: str | None = None
    expense_category: str | None = None
    apply_date: date | None = None
    payee_name: str | None = None
    payee_account: str | None = None
    reason_text: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UpdateDocumentCommand(BaseModel):
    """草稿或退回单据编辑请求，支持五类单据专属载荷。"""

    applicant_department: str | None = Field(default=None, max_length=128)
    budget_department: str | None = Field(default=None, max_length=128)
    expense_category: str | None = Field(default=None, max_length=64)
    apply_date: date | None = None
    total_amount: Decimal | None = Field(default=None, ge=Decimal("0.01"))
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    payee_name: str | None = Field(default=None, max_length=255)
    payee_account: str | None = Field(default=None, max_length=128)
    reason_text: str | None = Field(default=None, max_length=2000)
    line_items: list["DocumentLineItemCommand"] | None = None
    document_type: DocumentType | None = None
    document_payload: DocumentTypePayload | None = None
    expected_state_version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_payload_type(self) -> "UpdateDocumentCommand":
        """确保同时提供类型和 payload 时两者保持一致。"""
        if (
            self.document_type is not None
            and self.document_payload is not None
            and self.document_payload.document_type != self.document_type
        ):
            raise ValueError("单据类型与专属载荷类型不一致")
        return self


class DocumentActionCommand(BaseModel):
    """撤回或作废原因。"""

    reason: str = Field(min_length=1, max_length=500)


class DocumentSubmitCommand(BaseModel):
    """单据提交请求。"""

    reason: str = ""
    expected_state_version: int = Field(default=1, ge=1)


class DocumentLineItemResponse(BaseModel):
    """单据明细响应。"""

    item_id: UUID
    expense_item: str
    expense_date: date
    amount: Decimal
    currency: str
    invoice_no: str | None = None
    remark: str | None = None


class DocumentLineItemPatch(BaseModel):
    """单据明细局部更新请求。"""

    expense_item: str | None = Field(default=None, max_length=255)
    expense_date: date | None = None
    amount: Decimal | None = Field(default=None, gt=Decimal("0"))
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    invoice_no: str | None = Field(default=None, max_length=64)
    remark: str | None = Field(default=None, max_length=2000)


class DocumentPage(BaseModel):
    """单据分页响应。"""

    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentVersionResponse(BaseModel):
    """不可变版本响应。"""

    version_id: UUID
    document_id: UUID
    version_no: int
    created_by: UUID
    document_version_id: UUID | None = None
    analysis_task_id: UUID | None = None
    status: str | None = None
