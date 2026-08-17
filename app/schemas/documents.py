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


class DocumentVersionResponse(BaseModel):
    """不可变版本响应。"""

    version_id: UUID
    document_id: UUID
    version_no: int
    created_by: UUID
