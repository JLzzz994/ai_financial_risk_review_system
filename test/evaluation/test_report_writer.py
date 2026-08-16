"""九列报告测试。"""

import csv
from pathlib import Path

from evaluation.report_writer import HEADERS, write_report
from evaluation.schemas import EvaluationRow, MetricScores


def test_report_has_nine_columns(tmp_path: Path) -> None:
    """输出报告固定九列。"""
    row = EvaluationRow(question="q", reference_answer="a", generated_answer="a", context_evidence="e", scores=MetricScores(answer_correctness=1, faithfulness=1, context_relevance=1, context_recall=1, context_precision=1))
    output = write_report([row], tmp_path / "result.csv")
    with output.open(encoding="utf-8-sig", newline="") as stream:
        assert next(csv.reader(stream)) == HEADERS
