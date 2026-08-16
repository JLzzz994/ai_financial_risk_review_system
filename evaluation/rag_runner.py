"""RAG 流程评估入口。"""

from evaluation.schemas import GoldenQuestion, RagTrace
from evaluation.tools import EvaluationTools


def run_rag(sample: GoldenQuestion, tools: EvaluationTools) -> RagTrace:
    """调用工具生成答案并返回上下文证据。"""
    answer = tools.llm.generate(sample.question)
    evidence = sample.expected_evidence_ids
    return RagTrace(sample=sample, generated_answer=answer, context_evidence=evidence)
