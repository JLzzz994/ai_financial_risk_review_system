"""评估数据模型。"""

from pydantic import BaseModel, Field


class GoldenQuestion(BaseModel):
    """脱敏黄金问题。"""

    question_id: str
    question: str
    reference_answer: str
    document_version_id: str
    expected_evidence_ids: str
    category: str
    reviewer: str
    created_at: str
    enabled: bool = True


class RagTrace(BaseModel):
    """RAG 四要素轨迹。"""

    sample: GoldenQuestion
    generated_answer: str
    context_evidence: str


class MetricScores(BaseModel):
    """五大指标。"""

    answer_correctness: float = Field(ge=0, le=1)
    faithfulness: float = Field(ge=0, le=1)
    context_relevance: float = Field(ge=0, le=1)
    context_recall: float = Field(ge=0, le=1)
    context_precision: float = Field(ge=0, le=1)


class EvaluationRow(BaseModel):
    """严格九列评估结果。"""

    question: str
    reference_answer: str
    generated_answer: str
    context_evidence: str
    scores: MetricScores
