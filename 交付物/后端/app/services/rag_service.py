"""RAG 查询用例编排。"""

from app.errors import AppError
from engines.common.provider_registry import (
    ProviderKind,
    ProviderNotFoundError,
    ProviderRegistry,
)
from engines.model.contracts import RagEvidence
from engines.model.rag.errors import RagError


class RagService:
    """从 ProviderRegistry 获取 RAG，不直接依赖外部 SDK。"""

    def __init__(self, registry: ProviderRegistry) -> None:
        self.registry = registry

    async def retrieve(
        self,
        query: str,
        top_k: int,
        item_name: str | None = None,
    ) -> list[RagEvidence]:
        """执行制度依据检索并将下游错误映射为安全业务错误。"""
        try:
            adapter = self.registry.get(ProviderKind.RAG, "education-kb")
        except ProviderNotFoundError as exc:
            raise AppError("rag_not_configured", "RAG 检索能力尚未配置", 503) from exc
        try:
            return await adapter.retrieve(query, top_k, item_name=item_name)  # type: ignore[union-attr]
        except RagError as exc:
            status_code = 503 if exc.code != "rag_query_failed" else 422
            messages = {
                "rag_dependency_missing": "RAG 运行依赖尚未安装",
                "rag_unavailable": "RAG 知识库暂不可用",
                "rag_query_failed": "RAG 查询参数或结果无效",
            }
            raise AppError(exc.code, messages.get(exc.code, "RAG 检索失败"), status_code) from exc
        except Exception as exc:
            raise AppError("rag_unavailable", "RAG 知识库暂不可用", 503) from exc


__all__ = ["RagService"]
