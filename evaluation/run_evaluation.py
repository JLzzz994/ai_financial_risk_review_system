"""运行黄金问题集评估。"""

import csv
from pathlib import Path

from evaluation.metrics import score_trace
from evaluation.rag_runner import run_rag
from evaluation.report_writer import write_report
from evaluation.schemas import EvaluationRow, GoldenQuestion
from evaluation.tools import EvaluationTools


def read_golden_dataset(path: Path) -> list[GoldenQuestion]:
    """读取 UTF-8 CSV 黄金问题集。"""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [GoldenQuestion.model_validate(row) for row in csv.DictReader(stream)]


def evaluate_dataset(dataset_path: Path, output_path: Path, tools: EvaluationTools) -> Path:
    """依次执行 RAG、评分并输出九列结果。"""
    rows: list[EvaluationRow] = []
    for sample in read_golden_dataset(dataset_path):
        if not sample.enabled:
            continue
        trace = run_rag(sample, tools)
        rows.append(EvaluationRow(question=sample.question, reference_answer=sample.reference_answer, generated_answer=trace.generated_answer, context_evidence=trace.context_evidence, scores=score_trace(trace, tools)))
    return write_report(rows, output_path)
