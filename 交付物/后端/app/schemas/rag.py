"""RAG 查询 API 模型。"""

from pydantic import BaseModel, Field


class RagRetrieveRequest(BaseModel):
    """制度依据检索请求。"""

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    item_name: str | None = Field(default=None, min_length=1, max_length=256)


class RagEvidenceResponse(BaseModel):
    """制度依据检索结果，不承载财务附件证据。"""

    chunk_id: str
    content: str
    source_title: str
    score: float
    rule_version: str
    page_or_location: str | None = None
    item_name: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
