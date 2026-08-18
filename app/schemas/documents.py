"""费用报销单 API 模型。"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateDocumentCommand(BaseModel):
    """创建费用报销草稿。"""

    applicant_id: UUID
    applicant_department: str = Field(min_length=1, max_length=128)
    total_amount: Decimal = Field(ge=Decimal("0.01"), max_digits=18, decimal_places=2)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    apply_date: date
    reason_text: str = Field(min_length=1, max_length=2000)
    line_items: list["DocumentLineItemCommand"] = Field(default_factory=list)


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
    """草稿或退回单据编辑请求。"""

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
    expected_state_version: int = Field(default=1, ge=1)


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
    status: str | None = None
