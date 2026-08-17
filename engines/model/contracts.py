"""模型和 RAG 输入输出契约。"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """结构化字段抽取结果。"""

    fields: dict[str, str]
    confidence: float
    prompt_version: str


class LlmAdapter(Protocol):
    """LLM 适配器。"""

    async def extract(self, text: str, prompt_version: str) -> ExtractionResult:
        """从 OCR 文本抽取字段。"""


@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    """向量化请求，只携带待向量化的文本。"""

    text: str


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """确定维度的向量结果及模型版本。"""

    vector: tuple[float, ...]
    model_version: str


class EmbeddingAdapter(Protocol):
    """Embedding 服务适配器。"""

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        """将文本转换为向量。"""


class RagAdapter(Protocol):
    """制度和规则依据检索适配器。"""

    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        """返回规则证据摘要。"""
