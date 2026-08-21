"""OCR 输入输出契约。"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class OcrRequest:
    """OCR 请求，仅传对象键。"""

    attachment_id: UUID
    object_key: str


@dataclass(frozen=True, slots=True)
class OcrResult:
    """OCR 脱敏结果。"""

    attachment_id: UUID
    text: str
    page_count: int
    confidence: float


class OcrAdapter(Protocol):
    """私有化 OCR 服务适配器。"""

    async def recognize(self, request: OcrRequest) -> OcrResult:
        """识别附件文本。"""
