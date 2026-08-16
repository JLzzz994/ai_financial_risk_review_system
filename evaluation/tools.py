"""LLM 和 Embedding 工具适配器契约。"""

from typing import Protocol


class LlmTool(Protocol):
    """LLM 评审工具。"""

    def generate(self, prompt: str) -> str:
        """生成答案或评分结果。"""


class EmbeddingTool(Protocol):
    """Embedding 相似度工具。"""

    def similarity(self, left: str, right: str) -> float:
        """计算两个文本的相似度。"""


class EvaluationTools:
    """评估所需的两个工具。"""

    def __init__(self, llm: LlmTool, embedding: EmbeddingTool) -> None:
        """注入工具实现。"""
        self.llm = llm
        self.embedding = embedding
