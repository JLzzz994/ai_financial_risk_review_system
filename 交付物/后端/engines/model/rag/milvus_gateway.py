"""Milvus 混合搜索网关。

第三方 SDK 只允许出现在本模块，并且通过方法调用延迟导入。
"""

from collections.abc import Mapping, Sequence
from typing import Any, cast

from engines.model.rag.contracts import MilvusHit
from engines.model.rag.errors import (
    RagDependencyMissingError,
    RagNotConfiguredError,
    RagUnavailableError,
)


def build_item_name_expression(item_name: str) -> str:
    """构造 Milvus 字符串过滤表达式，并转义用户输入。"""
    escaped = item_name.replace("\\", "\\\\").replace("'", "\\'")
    return f"item_name == '{escaped}'"


def normalize_milvus_results(response: object) -> list[MilvusHit]:
    """把 MilvusClient 的响应转换为内部命中契约。"""
    if not isinstance(response, Sequence) or isinstance(response, (str, bytes)):
        return []
    rows: object = response[0] if response and isinstance(response[0], Sequence) else response
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return []
    hits: list[MilvusHit] = []
    for raw in rows:
        entity = _value(raw, "entity", {})
        if not isinstance(entity, Mapping):
            entity = {}
        chunk_id = _value(raw, "id", None) or entity.get("chunk_id")
        content = entity.get("content", "")
        source_title = entity.get("file_title") or entity.get("title") or ""
        if chunk_id is None or not isinstance(content, str) or not isinstance(source_title, str):
            continue
        metadata = {
            key: entity[key]
            for key in ("title", "parent_title", "part", "page", "position")
            if key in entity and entity[key] is not None
        }
        hits.append(
            MilvusHit(
                chunk_id=str(chunk_id),
                content=content,
                source_title=source_title,
                score=float(cast(Any, _value(raw, "distance", 0.0) or 0.0)),
                metadata=metadata,
                item_name=_as_optional_string(entity.get("item_name")),
            )
        )
    return hits


class MilvusGateway:
    """延迟创建 MilvusClient 并执行 BGE-M3 混合检索。"""

    def __init__(
        self,
        uri: str,
        collection_name: str,
        *,
        token: str = "",
        timeout_seconds: int = 10,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
    ) -> None:
        self.uri = uri
        self.collection_name = collection_name
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self._client: Any | None = None

    def _load_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.uri or not self.collection_name:
            raise RagNotConfiguredError("Milvus 地址或集合名未配置")
        try:
            from pymilvus import MilvusClient  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RagDependencyMissingError(
                "RAG 依赖未安装，请安装 requirements-rag.txt"
            ) from exc
        try:
            kwargs: dict[str, object] = {"uri": self.uri}
            if self.token:
                kwargs["token"] = self.token
            self._client = MilvusClient(**kwargs)
        except Exception as exc:
            raise RagUnavailableError("Milvus 服务不可用") from exc
        return self._client

    def hybrid_search(
        self,
        dense_vector: tuple[float, ...],
        sparse_vector: dict[int, float],
        *,
        top_k: int,
        item_name: str | None = None,
    ) -> list[MilvusHit]:
        """执行稠密+稀疏混合搜索并归一化响应。"""
        if top_k < 1:
            raise ValueError("top_k 必须大于 0")
        client = self._load_client()
        try:
            from pymilvus import AnnSearchRequest, WeightedRanker
        except ImportError as exc:
            raise RagDependencyMissingError(
                "RAG 依赖未安装，请安装 requirements-rag.txt"
            ) from exc
        expression = build_item_name_expression(item_name) if item_name else None
        try:
            requests = [
                AnnSearchRequest(
                    data=[list(dense_vector)],
                    anns_field="dense_vector",
                    param={"metric_type": "COSINE"},
                    expr=expression,
                    limit=top_k * 2,
                ),
                AnnSearchRequest(
                    data=[sparse_vector],
                    anns_field="sparse_vector",
                    param={"metric_type": "IP"},
                    expr=expression,
                    limit=top_k * 2,
                ),
            ]
            response = client.hybrid_search(
                collection_name=self.collection_name,
                reqs=requests,
                ranker=WeightedRanker(
                    self.dense_weight,
                    self.sparse_weight,
                    norm_score=True,
                ),
                limit=top_k,
                output_fields=[
                    "chunk_id",
                    "title",
                    "parent_title",
                    "file_title",
                    "item_name",
                    "content",
                    "part",
                ],
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            raise RagUnavailableError("Milvus 查询失败") from exc
        return normalize_milvus_results(response)


def _value(value: object, name: str, default: object) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _as_optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


__all__ = ["MilvusGateway", "build_item_name_expression", "normalize_milvus_results"]
