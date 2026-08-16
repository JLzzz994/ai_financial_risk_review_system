"""黄金问题集读取测试。"""

from pathlib import Path

from evaluation.run_evaluation import read_golden_dataset


def test_read_golden_dataset() -> None:
    """可读取 UTF-8 CSV。"""
    rows = read_golden_dataset(Path("evaluation/datasets/golden_questions.csv"))
    assert rows[0].question_id == "Q-0001"
