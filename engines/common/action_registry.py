"""Agent 可调用动作注册中心。

动作注册中心采用显式白名单，默认只允许查询和分析动作。审批决定、退回、
驳回等状态变更不是 Agent 动作，必须由审批服务统一处理，因此不会出现在
白名单中。
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ActionCategory(StrEnum):
    """允许 Agent 使用的动作类别。"""

    QUERY = "query"
    ANALYSIS = "analysis"


type ActionHandler = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    """可被 Agent 调用的动作定义。"""

    name: str
    handler: ActionHandler
    category: ActionCategory | None = None


class ActionRegistryError(Exception):
    """动作注册中心异常基类。"""


class ActionNotAllowedError(ActionRegistryError):
    """动作不在白名单中。"""


class ActionAlreadyRegisteredError(ActionRegistryError):
    """动作名称已被注册。"""


class ActionNotFoundError(ActionRegistryError):
    """请求的动作不存在。"""


class ActionRegistry:
    """为 Agent 提供只读查询和分析动作的显式注册中心。"""

    _ALLOWLIST_CATEGORIES: dict[str, ActionCategory] = {
        "document.query": ActionCategory.QUERY,
        "document.analyze": ActionCategory.ANALYSIS,
        "supplier.query": ActionCategory.QUERY,
        "supplier.analyze": ActionCategory.ANALYSIS,
        "market_price.query": ActionCategory.QUERY,
        "policy.retrieve": ActionCategory.QUERY,
        "risk.explain": ActionCategory.ANALYSIS,
        "risk.evidence": ActionCategory.ANALYSIS,
    }
    DEFAULT_ALLOWLIST: frozenset[str] = frozenset(_ALLOWLIST_CATEGORIES)

    def __init__(self) -> None:
        """创建空动作注册中心，白名单不可被调用方扩展。"""
        self._actions: dict[str, ActionDefinition] = {}

    def register(self, action: ActionDefinition) -> ActionDefinition:
        """注册白名单动作，拒绝未知动作和重复名称。"""
        action_name = action.name.strip()
        if action_name not in self.DEFAULT_ALLOWLIST:
            raise ActionNotAllowedError(
                f"动作不在 Agent 白名单中：{action_name}"
            )
        expected_category = self._ALLOWLIST_CATEGORIES[action_name]
        if action.category is not None and action.category != expected_category:
            raise ActionNotAllowedError(
                f"动作类别与白名单不匹配：{action_name}"
            )
        if action_name in self._actions:
            raise ActionAlreadyRegisteredError(f"动作已注册：{action_name}")
        if not callable(action.handler):
            raise TypeError(f"动作处理器不可调用：{action_name}")

        # 领域对象保持规范化名称，避免注册时的空白字符造成查询不一致；
        # 已经规范化的调用方对象原样保留，便于依赖注入和测试按身份复用。
        registered_action = (
            action
            if action.name == action_name and action.category == expected_category
            else ActionDefinition(
                name=action_name,
                handler=action.handler,
                category=expected_category,
            )
        )
        self._actions[action_name] = registered_action
        return registered_action

    def get(self, name: str) -> ActionDefinition:
        """查询已注册动作；未知或未注册动作均返回明确异常。"""
        action_name = name.strip()
        action = self._actions.get(action_name)
        if action is None:
            raise ActionNotFoundError(f"未找到已注册动作：{action_name}")
        return action

    def list_actions(self) -> tuple[ActionDefinition, ...]:
        """返回动作快照，不暴露内部可变字典。"""
        return tuple(self._actions.values())


__all__ = [
    "ActionAlreadyRegisteredError",
    "ActionCategory",
    "ActionDefinition",
    "ActionHandler",
    "ActionNotAllowedError",
    "ActionNotFoundError",
    "ActionRegistry",
    "ActionRegistryError",
]
