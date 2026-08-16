"""评估五大指标。"""

from evaluation.schemas import MetricScores, RagTrace
from evaluation.tools import EvaluationTools


def score_trace(trace: RagTrace, tools: EvaluationTools) -> MetricScores:
    """使用 LLM/Embedding 适配器计算五大指标。"""
    similarity = max(0.0, min(1.0, tools.embedding.similarity(trace.generated_answer, trace.sample.reference_answer)))
    evidence_score = 1.0 if trace.context_evidence.strip() else 0.0
    return MetricScores(answer_correctness=similarity, faithfulness=evidence_score, context_relevance=evidence_score, context_recall=evidence_score, context_precision=evidence_score)
