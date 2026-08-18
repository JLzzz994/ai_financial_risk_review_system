"""应用外部能力组装点。"""

from app.config import settings
from engines.common.provider_registry import ProviderKind, ProviderRegistry
from engines.common.storage import FileStorage
from engines.ocr.paddleocr_adapter import PaddleOCRAdapter


def build_provider_registry(storage: FileStorage) -> ProviderRegistry:
    """注册生产默认 FileStorage 与 PaddleOCR，业务层不直接依赖 SDK。"""
    registry = ProviderRegistry()
    registry.register(ProviderKind.FILE_STORAGE, "default", storage)
    model_dir = settings.ocr_model if settings.ocr_model not in {"", "default"} else None
    registry.register(
        ProviderKind.OCR,
        "paddleocr",
        PaddleOCRAdapter(storage, language="ch", model_dir=model_dir),
    )
    return registry


__all__ = ["build_provider_registry"]
