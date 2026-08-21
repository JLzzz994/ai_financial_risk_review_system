"""RAG 适配层的内部命中契约。"""

from dataclasses import dataclass, field

from engines.model.contracts import RagEvidence


@dataclass(frozen=True, slots=True)
class MilvusHit:
    """Milvus dense/sparse 搜索返回的最小字段集合。"""

    chunk_id: str
    content: str
    source_title: str
    score: float
    metadata: dict[str, object] = field(default_factory=dict)
    item_name: str | None = None


__all__ = ["MilvusHit", "RagEvidence"]
