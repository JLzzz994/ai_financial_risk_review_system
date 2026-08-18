"""PaddleOCR 3.x 文件识别适配器。

该模块只依赖 ``FileStorage`` 和 OCR 窄契约。PaddleOCR SDK 在真正创建默认
pipeline 时才导入，测试和其他环境可以注入兼容的 fake pipeline。
"""

import asyncio
import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from engines.common.storage import FileStorage
from engines.ocr.contracts import OcrRequest, OcrResult


class OcrAdapterError(RuntimeError):
    """OCR 适配器异常基类。"""


class OcrConfigurationError(OcrAdapterError):
    """OCR SDK 或模型配置不可用。"""


class OcrObjectNotFoundError(OcrAdapterError):
    """待识别对象不存在或不可读取。"""


class OcrProcessingError(OcrAdapterError):
    """OCR 推理失败。"""


class PaddleOCRAdapter:
    """通过对象存储和 PaddleOCR 3.x pipeline 执行异步 OCR。"""

    provider_name = "paddleocr"
    provider_version = "3.x"

    def __init__(
        self,
        storage: FileStorage,
        pipeline: object | None = None,
        *,
        language: str = "ch",
        model_dir: str | None = None,
        max_text_length: int = 20_000,
    ) -> None:
        """注入对象存储与可选 pipeline；未注入时延迟创建 PaddleOCR。"""
        if max_text_length < 1:
            raise ValueError("OCR 文本长度上限必须为正数")
        self.storage = storage
        self._pipeline = pipeline
        self.language = language
        self.model_dir = model_dir
        self.max_text_length = max_text_length

    async def recognize(self, request: OcrRequest) -> OcrResult:
        """读取版本附件并在线程中执行 PaddleOCR，返回脱敏聚合结果。"""
        if not request.object_key.strip():
            raise OcrObjectNotFoundError("OCR 对象键为空")
        try:
            content = await asyncio.to_thread(self.storage.get, request.object_key)
        except (FileNotFoundError, OSError) as exc:
            raise OcrObjectNotFoundError("OCR 对象不可读取") from exc
        except Exception as exc:
            raise OcrObjectNotFoundError("OCR 对象读取失败") from exc

        try:
            text, page_count, confidence = await asyncio.to_thread(
                self._recognize_bytes,
                content,
                Path(request.object_key).suffix or ".bin",
            )
        except OcrAdapterError:
            raise
        except Exception as exc:
            raise OcrProcessingError("OCR 识别失败") from exc
        return OcrResult(request.attachment_id, text, page_count, confidence)

    def _recognize_bytes(self, content: bytes, suffix: str) -> tuple[str, int, float]:
        """在受限临时文件中调用 pipeline，并删除文件。"""
        pipeline = self._get_pipeline()
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=suffix, prefix="financial-ocr-", delete=False
            ) as temporary:
                os.chmod(temporary.name, 0o600)
                temporary.write(content)
                temp_path = temporary.name
            predict = getattr(pipeline, "predict", None)
            if not callable(predict):
                raise OcrProcessingError("PaddleOCR pipeline 缺少 predict 方法")
            # PaddleOCR 3.x 的示例使用位置参数传入文件路径；这样也兼容
            # 仅声明单个 ``source`` 位置参数的私有化 pipeline 包装器。
            raw_results = predict(temp_path)
            return self._aggregate_results(raw_results)
        except OcrAdapterError:
            raise
        except Exception as exc:
            raise OcrProcessingError("PaddleOCR 推理失败") from exc
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def _get_pipeline(self) -> object:
        """延迟导入并构造 PaddleOCR 3.x pipeline。"""
        if self._pipeline is not None:
            return self._pipeline
        try:
            module = import_module("paddleocr")
            kwargs: dict[str, Any] = {
                "lang": self.language,
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
                "use_textline_orientation": False,
            }
            if self.model_dir:
                kwargs["text_detection_model_dir"] = self.model_dir
            self._pipeline = module.PaddleOCR(**kwargs)
            return self._pipeline
        except ImportError as exc:
            raise OcrConfigurationError("PaddleOCR SDK 未安装") from exc
        except Exception as exc:
            raise OcrConfigurationError("PaddleOCR 模型配置不可用") from exc

    def _aggregate_results(self, raw_results: object) -> tuple[str, int, float]:
        """兼容 PaddleOCR 结果对象和字典，聚合文本、页数及平均置信度。"""
        if raw_results is None:
            return "", 0, 0.0
        if isinstance(raw_results, Mapping) or hasattr(raw_results, "rec_texts"):
            pages: list[object] = [raw_results]
        elif isinstance(raw_results, Iterable) and not isinstance(raw_results, (str, bytes)):
            pages = list(cast(Iterable[object], raw_results))
        else:
            pages = [raw_results]

        texts: list[str] = []
        scores: list[float] = []
        for page in pages:
            page_texts = self._read_value(page, "rec_texts", "texts", "text")
            page_scores = self._read_value(page, "rec_scores", "scores", "confidence")
            texts.extend(self._string_values(page_texts))
            scores.extend(self._float_values(page_scores))
        text = "\n".join(value for value in texts if value).strip()
        if len(text) > self.max_text_length:
            text = text[: self.max_text_length - 1] + "…"
        confidence = sum(scores) / len(scores) if scores else 0.0
        return text, len(pages), max(0.0, min(1.0, confidence))

    @staticmethod
    def _read_value(page: object, *names: str) -> object:
        """从字典、PaddleOCR 结果对象或 JSON 风格对象取字段。"""
        for name in names:
            if isinstance(page, Mapping) and name in page:
                return page[name]
            value = getattr(page, name, None)
            if value is not None:
                return value
        return []

    @staticmethod
    def _string_values(value: object) -> list[str]:
        """将结果字段转换为安全字符串序列。"""
        if isinstance(value, str):
            return [value]
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if value else []

    @staticmethod
    def _float_values(value: object) -> list[float]:
        """过滤无法解析和越界的置信度。"""
        values = [value] if isinstance(value, (int, float, str)) else value
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            return []
        result: list[float] = []
        for item in values:
            try:
                score = float(item)
            except (TypeError, ValueError):
                continue
            if 0 <= score <= 1:
                result.append(score)
        return result


__all__ = [
    "OcrAdapterError",
    "OcrConfigurationError",
    "OcrObjectNotFoundError",
    "OcrProcessingError",
    "PaddleOCRAdapter",
]
