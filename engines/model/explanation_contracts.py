"""风险解释模型契约。

与字段抽取 LLM 分离，避免一个宽接口同时承担 OCR 后抽取和风险解释两类职责。
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExplanationRequest:
    prompt: str
    rule_code: str
    risk_level: str
    finding_status: str


@dataclass(frozen=True, slots=True)
class ExplanationResult:
    explanation: str
    suggestion: str
    model_version: str
    prompt_version: str


class ExplanationAdapter(Protocol):
    """只能解释既有风险事实，不拥有修改规则结果的能力。"""

    async def explain(self, request: ExplanationRequest) -> ExplanationResult:
        """返回风险解释和处理建议。"""


__all__ = ["ExplanationAdapter", "ExplanationRequest", "ExplanationResult"]
