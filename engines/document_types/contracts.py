"""五类单据专属字段的强类型契约与确定性校验。"""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from engines.expense_reimbursement.contracts import ExpenseLine
from engines.expense_reimbursement.validators import validate_expense_lines


class DocumentType(StrEnum):
    """MVP 支持的五类单据编码。"""

    PUBLIC_PAYMENT = "public_payment"
    PREPAYMENT = "prepayment"
    BATCH_PAYMENT = "batch_payment"
    EXPENSE_REIMBURSEMENT = "expense_reimbursement"
    TRAVEL_REIMBURSEMENT = "travel_reimbursement"


def _validate_decimal_amount(value: object) -> object:
    """拒绝 float，并保证金额不为负且最多两位小数。"""
    if isinstance(value, float):
        raise ValueError("金额不得使用 float")
    if isinstance(value, Decimal):
        exponent = value.as_tuple().exponent
        if value < 0 or not isinstance(exponent, int) or exponent < -2:
            raise ValueError("金额不得为负且最多两位小数")
    return value


Amount = Annotated[
    Decimal,
    BeforeValidator(_validate_decimal_amount),
    Field(ge=Decimal("0"), max_digits=18, decimal_places=2),
]


class BaseDocumentTypePayload(BaseModel):
    """五类单据专属字段的通用约束。"""

    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    currency: str = "CNY"

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        """校验币种仅为三位大写的 MVP 币种 CNY。"""
        if value != "CNY":
            raise ValueError("MVP 仅支持三位大写币种 CNY")
        return value


class PaymentPayload(BaseDocumentTypePayload):
    """对公付款和预付款共用的专属字段。"""

    contract_no: str = Field(min_length=1, max_length=128)
    supplier_name: str = Field(min_length=1, max_length=255)
    payment_ratio: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    payment_terms: str = Field(min_length=1, max_length=2000)
    planned_payment_date: date

    @field_validator("payment_ratio", mode="before")
    @classmethod
    def validate_payment_ratio_type(cls, value: object) -> object:
        """保证付款比例使用 Decimal 而非 float。"""
        if isinstance(value, float):
            raise ValueError("付款比例不得使用 float")
        return value


class PublicPaymentPayload(PaymentPayload):
    """对公付款专属字段。"""

    document_type: Literal[DocumentType.PUBLIC_PAYMENT] = DocumentType.PUBLIC_PAYMENT


class PrepaymentPayload(PaymentPayload):
    """预付款专属字段。"""

    document_type: Literal[DocumentType.PREPAYMENT] = DocumentType.PREPAYMENT


class BatchPaymentDetail(BaseModel):
    """批量付款中的一笔收款明细。"""

    model_config = ConfigDict(extra="forbid")

    payee_name: str = Field(min_length=1, max_length=255)
    amount: Amount

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: object) -> object:
        """校验单笔金额类型与精度。"""
        return _validate_decimal_amount(value)


class BatchPaymentPayload(BaseDocumentTypePayload):
    """批量付款专属字段。"""

    document_type: Literal[DocumentType.BATCH_PAYMENT] = DocumentType.BATCH_PAYMENT
    payment_details: list[BatchPaymentDetail] = Field(min_length=1)
    total_amount: Amount
    payment_count: int = Field(ge=1)

    @field_validator("total_amount", mode="before")
    @classmethod
    def validate_total_amount(cls, value: object) -> object:
        """校验批次总金额类型与精度。"""
        return _validate_decimal_amount(value)

    @model_validator(mode="after")
    def validate_batch_consistency(self) -> "BatchPaymentPayload":
        """校验付款笔数及批次总金额与明细保持一致。"""
        if self.payment_count != len(self.payment_details):
            raise ValueError("付款笔数必须等于付款明细条数")
        detail_total = sum((item.amount for item in self.payment_details), Decimal("0.00"))
        if self.total_amount != detail_total:
            raise ValueError("批次总金额必须等于付款明细金额之和")
        return self


class ExpenseReimbursementDetail(BaseModel):
    """费用报销中的一笔扩展费用明细。"""

    model_config = ConfigDict(extra="forbid")

    expense_item: str = Field(min_length=1, max_length=255)
    consumption_date: date
    consumption_location: str = Field(min_length=1, max_length=255)
    expense_category: str = Field(min_length=1, max_length=64)
    reimbursement_amount: Amount
    currency: str = "CNY"

    @field_validator("reimbursement_amount", mode="before")
    @classmethod
    def validate_reimbursement_amount(cls, value: object) -> object:
        """校验报销金额类型与精度。"""
        return _validate_decimal_amount(value)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        """校验明细币种仅为 CNY。"""
        if value != "CNY":
            raise ValueError("MVP 仅支持三位大写币种 CNY")
        return value

    def to_expense_line(self) -> ExpenseLine:
        """转换为既有费用报销领域对象以复用原有校验。"""
        return ExpenseLine(self.expense_item, self.reimbursement_amount, self.currency)


class ExpenseReimbursementPayload(BaseDocumentTypePayload):
    """费用报销专属字段，兼容既有费用报销领域校验。"""

    document_type: Literal[DocumentType.EXPENSE_REIMBURSEMENT] = DocumentType.EXPENSE_REIMBURSEMENT
    expense_details: list[ExpenseReimbursementDetail] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_expense_details(self) -> "ExpenseReimbursementPayload":
        """复用既有费用明细和币种一致性校验。"""
        validate_expense_lines(
            [detail.to_expense_line() for detail in self.expense_details],
            self.currency,
        )
        return self


class TravelReimbursementPayload(BaseDocumentTypePayload):
    """差旅报销专属字段。"""

    document_type: Literal[DocumentType.TRAVEL_REIMBURSEMENT] = DocumentType.TRAVEL_REIMBURSEMENT
    travel_location: str = Field(min_length=1, max_length=255)
    travel_start_date: date
    travel_end_date: date
    transportation_amount: Amount
    accommodation_amount: Amount
    meal_amount: Amount
    allowance_amount: Amount

    @field_validator(
        "transportation_amount",
        "accommodation_amount",
        "meal_amount",
        "allowance_amount",
        mode="before",
    )
    @classmethod
    def validate_travel_amounts(cls, value: object) -> object:
        """校验四类差旅金额类型与精度。"""
        return _validate_decimal_amount(value)

    @model_validator(mode="after")
    def validate_travel_dates(self) -> "TravelReimbursementPayload":
        """校验出差结束日期不早于开始日期。"""
        if self.travel_end_date < self.travel_start_date:
            raise ValueError("出差结束日期不得早于开始日期")
        return self

    @property
    def total_amount(self) -> Decimal:
        """计算四类差旅费用的精确合计。"""
        return sum(
            (
                self.transportation_amount,
                self.accommodation_amount,
                self.meal_amount,
                self.allowance_amount,
            ),
            Decimal("0.00"),
        )


DocumentTypePayload: TypeAlias = (
    PublicPaymentPayload
    | PrepaymentPayload
    | BatchPaymentPayload
    | ExpenseReimbursementPayload
    | TravelReimbursementPayload
)

_PAYLOAD_MODELS: dict[DocumentType, type[DocumentTypePayload]] = {
    DocumentType.PUBLIC_PAYMENT: PublicPaymentPayload,
    DocumentType.PREPAYMENT: PrepaymentPayload,
    DocumentType.BATCH_PAYMENT: BatchPaymentPayload,
    DocumentType.EXPENSE_REIMBURSEMENT: ExpenseReimbursementPayload,
    DocumentType.TRAVEL_REIMBURSEMENT: TravelReimbursementPayload,
}


def validate_document_type_payload(
    document_type: str | DocumentType,
    payload: Mapping[str, Any],
) -> DocumentTypePayload:
    """按单据类型分派并返回已规范化的专属字段模型。"""
    try:
        normalized_type = DocumentType(document_type)
    except ValueError as exc:
        raise ValueError(f"不支持的单据类型: {document_type}") from exc
    return _PAYLOAD_MODELS[normalized_type].model_validate(payload)
