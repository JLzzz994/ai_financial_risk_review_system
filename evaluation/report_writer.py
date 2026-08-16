"""九列评估报告输出。"""

import csv
from pathlib import Path

from evaluation.schemas import EvaluationRow

HEADERS = ["question", "reference_answer", "generated_answer", "context_evidence", "answer_correctness", "faithfulness", "context_relevance", "context_recall", "context_precision"]


def write_report(rows: list[EvaluationRow], output_path: Path) -> Path:
    """将评估结果严格写为九列 UTF-8 CSV。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        for row in rows:
            writer.writerow([row.question, row.reference_answer, row.generated_answer, row.context_evidence, row.scores.answer_correctness, row.scores.faithfulness, row.scores.context_relevance, row.scores.context_recall, row.scores.context_precision])
    return output_path
