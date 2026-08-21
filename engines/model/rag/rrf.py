"""稠密/稀疏结果的 Reciprocal Rank Fusion。"""

from collections import OrderedDict

from engines.model.rag.contracts import MilvusHit


def reciprocal_rank_fusion(
    *ranked_lists: list[MilvusHit], k: int = 60
) -> list[MilvusHit]:
    """按 RRF 分数融合多个已排序命中列表。"""
    if k < 1:
        raise ValueError("RRF k 必须大于 0")
    scores: dict[str, float] = {}
    hits: OrderedDict[str, MilvusHit] = OrderedDict()
    for ranked in ranked_lists:
        for rank, hit in enumerate(ranked, start=1):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
            hits.setdefault(hit.chunk_id, hit)
    return [
        MilvusHit(
            chunk_id=hit.chunk_id,
            content=hit.content,
            source_title=hit.source_title,
            score=scores[hit.chunk_id],
            metadata=hit.metadata,
            item_name=hit.item_name,
        )
        for hit in sorted(hits.values(), key=lambda item: scores[item.chunk_id], reverse=True)
    ]
