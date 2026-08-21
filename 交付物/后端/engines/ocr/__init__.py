"""OCR 适配器与输入输出契约。"""

from engines.ocr.contracts import OcrAdapter, OcrRequest, OcrResult
from engines.ocr.paddleocr_adapter import (
    OcrAdapterError,
    OcrConfigurationError,
    OcrObjectNotFoundError,
    OcrProcessingError,
    PaddleOCRAdapter,
)

__all__ = [
    "OcrAdapter",
    "OcrAdapterError",
    "OcrConfigurationError",
    "OcrObjectNotFoundError",
    "OcrProcessingError",
    "OcrRequest",
    "OcrResult",
    "PaddleOCRAdapter",
]
