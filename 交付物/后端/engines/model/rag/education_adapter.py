"""教育知识库 Milvus/BGE-M3 适配器。"""

import asyncio
from typing import Protocol

from engines.model.contracts import RagEvidence
from engines.model.rag.contracts import MilvusHit
from engines.model.rag.embedding import HybridEmbeddingResult
from engines.model.rag.errors import RagError, RagQueryError


class EmbeddingLike(Protocol):
    """RAG 组合器所需的最小向量化接口。"""

    def embed(self, text: str) -> HybridEmbeddingResult:
        """同步生成混合向量。"""


class GatewayLike(Protocol):
    """RAG 组合器所需的最小 Milvus 接口。"""

    def hybrid_search(
        self,
        dense_vector: tuple[float, ...],
        sparse_vector: dict[int, float],
        *,
        top_k: int,
        item_name: str | None = None,
    ) -> list[MilvusHit]:
        """同步执行混合检索。"""


class RerankerLike(Protocol):
    """RAG 组合器所需的最小重排接口。"""

    def rerank(self, query: str, hits: list[MilvusHit], top_k: int) -> list[MilvusHit]:
        """同步重排候选。"""


class EducationKnowledgeRagAdapter:
    """将外部教育知识库的检索能力收敛为当前项目的 RagAdapter。"""

    def __init__(
        self,
        *,
        embedding: EmbeddingLike,
        gateway: GatewayLike,
        reranker: RerankerLike | None = None,
        rule_version: str = "v1",
    ) -> None:
        self.embedding = embedding
        self.gateway = gateway
        self.reranker = reranker
        self.rule_version = rule_version

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        item_name: str | None = None,
    ) -> list[RagEvidence]:
        """检索制度依据并返回不包含附件事实的结构化证据。"""
        if not query.strip():
            raise RagQueryError("查询文本不能为空")
        if not 1 <= top_k <= 50:
            raise RagQueryError("top_k 必须在 1 到 50 之间")
        try:
            embedding = await asyncio.to_thread(self.embedding.embed, query)
            hits = await asyncio.to_thread(
                self.gateway.hybrid_search,
                embedding.dense,
                embedding.sparse,
                top_k=top_k,
                item_name=item_name,
            )
            if self.reranker is not None:
                hits = await asyncio.to_thread(self.reranker.rerank, query, hits, top_k)
            return [self._to_evidence(hit) for hit in hits[:top_k]]
        except RagError:
            raise
        except Exception as exc:
            raise RagQueryError("RAG 查询失败") from exc

    def _to_evidence(self, hit: MilvusHit) -> RagEvidence:
        location = hit.metadata.get("page") or hit.metadata.get("position")
        page_or_location = location if isinstance(location, str) else None
        return RagEvidence(
            chunk_id=hit.chunk_id,
            content=hit.content,
            source_title=hit.source_title,
            score=float(hit.score),
            rule_version=self.rule_version,
            page_or_location=page_or_location,
            item_name=hit.item_name,
            metadata=dict(hit.metadata),
        )


__all__ = ["EducationKnowledgeRagAdapter"]
