"""外部 BGE Reranker HTTP 适配器。"""

from collections.abc import Mapping, Sequence
from typing import Any

from engines.model.rag.contracts import MilvusHit
from engines.model.rag.errors import (
    RagDependencyMissingError,
    RagNotConfiguredError,
    RagQueryError,
    RagUnavailableError,
)


def _new_http_client(*, timeout: float, headers: dict[str, str]) -> Any:
    """延迟创建 HTTP 客户端，确保 RAG 关闭时不要求导入 httpx。"""

    try:
        import httpx
    except ImportError as exc:
        raise RagDependencyMissingError(
            "RAG HTTP 依赖未安装，请安装 requirements-rag.txt"
        ) from exc
    return httpx.Client(timeout=timeout, headers=headers)


class HttpBgeReranker:
    """调用外部 BGE Reranker 服务对 Milvus 候选重排。"""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str = "",
        timeout_seconds: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def rerank(self, query: str, hits: list[MilvusHit], top_k: int) -> list[MilvusHit]:
        """按查询相关性重排，未配置服务时明确报错。"""
        if not hits:
            return hits[:top_k]
        if not self.base_url:
            raise RagNotConfiguredError("未配置外部 BGE Reranker 服务地址")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            with _new_http_client(timeout=self.timeout_seconds, headers=headers) as client:
                response = client.post(
                    f"{self.base_url}/rerank",
                    json={"query": query, "documents": [hit.content for hit in hits]},
                    headers=headers,
                )
        except RagDependencyMissingError:
            raise
        except Exception as exc:
            raise RagUnavailableError("外部 BGE Reranker 服务不可用") from exc
        if getattr(response, "status_code", 500) >= 400:
            raise RagUnavailableError("外部 BGE Reranker 服务返回错误")
        try:
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise RagQueryError("BGE Reranker 服务响应格式无效")
            payload_data = payload.get("data", payload)
            if not isinstance(payload_data, Mapping):
                raise RagQueryError("BGE Reranker 服务响应格式无效")
            scores = _extract_scores(payload_data)
            if len(scores) != len(hits):
                raise RagQueryError("BGE Reranker 分数数量与候选不一致")
            ranked = [
                MilvusHit(
                    chunk_id=hit.chunk_id,
                    content=hit.content,
                    source_title=hit.source_title,
                    score=score,
                    metadata=hit.metadata,
                    item_name=hit.item_name,
                )
                for hit, score in zip(hits, scores, strict=True)
            ]
        except Exception as exc:
            if isinstance(exc, RagQueryError):
                raise
            raise RagQueryError("RAG 重排失败") from exc
        return sorted(ranked, key=lambda hit: hit.score, reverse=True)[:top_k]


def _extract_scores(payload: Mapping[str, object]) -> list[float]:
    """兼容简单 scores 数组及常见 results 对象数组。"""
    raw_scores = payload.get("scores")
    if raw_scores is None:
        raw_results = payload.get("results")
        if not isinstance(raw_results, Sequence):
            raise RagQueryError("BGE Reranker 分数格式无效")
        raw_scores = [
            item.get("score") if isinstance(item, Mapping) else None for item in raw_results
        ]
    if not isinstance(raw_scores, Sequence) or isinstance(raw_scores, (str, bytes)):
        raise RagQueryError("BGE Reranker 分数格式无效")
    try:
        return [float(score) for score in raw_scores]
    except (TypeError, ValueError) as exc:
        raise RagQueryError("BGE Reranker 分数格式无效") from exc


__all__ = ["HttpBgeReranker"]
