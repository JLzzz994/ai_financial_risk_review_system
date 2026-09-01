"""平台账单 OCR/Excel 解析后的标准化契约。

本模块不绑定 PaddleOCR SDK。OCR/Excel 适配器负责输出字段及证据位置，领域层只消费
统一结构，因此生产环境可替换 PP-OCRv4、表格解析服务或平台 CSV/Excel 直读实现。
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ParsedField(BaseModel):
    """一个带证据定位的标准化字段。"""

    name: str
    value: str
    page_or_location: str
    original_text: str
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))


class ParsedReconciliationRow(BaseModel):
    """平台账单中的单行对账事实。"""

    platform: str
    shop_name: str
    order_no: str
    settlement_no: str | None = None
    expected_receivable: Decimal | None = None
    settlement_amount: Decimal | None = None
    refund_amount: Decimal = Decimal("0")
    adjustment_amount: Decimal = Decimal("0")
    actual_received_amount: Decimal | None = None
    settlement_subject: str | None = None
    payment_subject: str | None = None
    source_kind: Literal["ocr", "excel", "api"]
    fields: list[ParsedField] = Field(default_factory=list)

    @property
    def minimum_confidence(self) -> Decimal | None:
        """关键字段采用最小置信度，避免平均值掩盖单字段低置信度。"""
        if not self.fields:
            return None
        return min(item.confidence for item in self.fields)

    def missing_key_fields(self) -> list[str]:
        """返回无法自动对账的关键字段。"""
        missing: list[str] = []
        if not self.order_no.strip():
            missing.append("order_no")
        if self.expected_receivable is None:
            missing.append("expected_receivable")
        if self.settlement_amount is None:
            missing.append("settlement_amount")
        return missing


__all__ = ["ParsedField", "ParsedReconciliationRow"]
