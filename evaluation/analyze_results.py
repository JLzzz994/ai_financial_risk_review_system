"""评估结果和 bad case 分析。"""

import csv
from pathlib import Path


def analyze_results(result_path: Path, threshold: float = 0.6) -> list[dict[str, str]]:
    """筛选任一指标低于阈值的样本摘要，供后续查日志定位。"""
    bad_cases: list[dict[str, str]] = []
    with result_path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            metric_values = [float(row[name]) for name in ("answer_correctness", "faithfulness", "context_relevance", "context_recall", "context_precision")]
            if min(metric_values) < threshold:
                bad_cases.append({"question": row["question"], "lowest_score": str(min(metric_values))})
    return bad_cases
