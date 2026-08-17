"""外部能力 Provider 注册中心。

业务服务只依赖本模块暴露的注册和查询能力，不直接依赖 OCR、模型或对象存储
厂商 SDK。注册中心的 key 由 ``ProviderKind`` 和名称共同组成，避免不同能力
使用同名 provider 时发生覆盖。
"""

from dataclasses import dataclass
from enum import StrEnum

from engines.common.storage import FileStorage
from engines.model.contracts import EmbeddingAdapter, LlmAdapter, RagAdapter
from engines.ocr.contracts import OcrAdapter


class ProviderKind(StrEnum):
    """系统允许注册的外部能力类别。"""

    OCR = "ocr"
    LLM = "llm"
    EMBEDDING = "embedding"
    RAG = "rag"
    FILE_STORAGE = "file_storage"


type ProviderImplementation = (
    OcrAdapter | LlmAdapter | EmbeddingAdapter | RagAdapter | FileStorage
)


@dataclass(frozen=True, slots=True)
class ProviderRegistration:
    """一个已注册 provider 的不可变描述。"""

    kind: ProviderKind
    name: str
    provider: ProviderImplementation


class ProviderRegistryError(Exception):
    """Provider 注册中心异常基类。"""


class ProviderAlreadyRegisteredError(ProviderRegistryError):
    """同一能力类别下 provider 名称已存在。"""


class ProviderNotFoundError(ProviderRegistryError):
    """请求的 provider 不存在。"""


class ProviderKindError(ProviderRegistryError):
    """provider 能力类别无效。"""


class ProviderRegistry:
    """按能力类别和名称管理外部适配器。"""

    _REQUIRED_METHODS: dict[ProviderKind, tuple[str, ...]] = {
        ProviderKind.OCR: ("recognize",),
        ProviderKind.LLM: ("extract",),
        ProviderKind.EMBEDDING: ("embed",),
        ProviderKind.RAG: ("retrieve",),
        ProviderKind.FILE_STORAGE: ("put", "get", "delete", "create_presigned_url"),
    }

    def __init__(self) -> None:
        """创建空注册中心。"""
        self._providers: dict[ProviderKind, dict[str, ProviderRegistration]] = {
            kind: {} for kind in ProviderKind
        }

    def register(
        self,
        kind: ProviderKind | str,
        name: str,
        provider: ProviderImplementation,
    ) -> ProviderRegistration:
        """注册 provider，并拒绝重复名称和不兼容实现。

        ``provider`` 只能通过窄接口接入；即使对象实现了某个方法，也必须与
        指定的能力类别匹配，否则调用方会在任务运行时遇到隐蔽错误。
        """
        provider_kind = self._normalize_kind(kind)
        provider_name = self._normalize_name(name)
        providers = self._providers[provider_kind]
        if provider_name in providers:
            raise ProviderAlreadyRegisteredError(
                f"{provider_kind.value} provider 已注册：{provider_name}"
            )
        if not self._is_compatible(provider_kind, provider):
            raise TypeError(
                f"provider 与 {provider_kind.value} 类型不兼容：{provider_name}"
            )

        registration = ProviderRegistration(provider_kind, provider_name, provider)
        providers[provider_name] = registration
        return registration

    def get(self, kind: ProviderKind | str, name: str) -> ProviderImplementation:
        """按能力类别和名称查询 provider，不存在时抛出明确异常。"""
        provider_kind = self._normalize_kind(kind)
        provider_name = self._normalize_name(name)
        registration = self._providers[provider_kind].get(provider_name)
        if registration is None:
            raise ProviderNotFoundError(
                f"未找到 {provider_kind.value} provider：{provider_name}"
            )
        return registration.provider

    def get_registration(
        self, kind: ProviderKind | str, name: str
    ) -> ProviderRegistration:
        """按类别和名称返回包含元数据的不可变注册记录。"""
        provider_kind = self._normalize_kind(kind)
        provider_name = self._normalize_name(name)
        registration = self._providers[provider_kind].get(provider_name)
        if registration is None:
            raise ProviderNotFoundError(
                f"未找到 {provider_kind.value} provider：{provider_name}"
            )
        return registration

    def list_registrations(self, kind: ProviderKind | str) -> tuple[ProviderRegistration, ...]:
        """返回某能力类别的 provider 快照，避免暴露内部可变容器。"""
        provider_kind = self._normalize_kind(kind)
        return tuple(self._providers[provider_kind].values())

    @staticmethod
    def _normalize_kind(kind: ProviderKind | str) -> ProviderKind:
        """将字符串类别转换为枚举，并给出明确错误。"""
        try:
            return ProviderKind(kind)
        except ValueError as exc:
            raise ProviderKindError(f"不支持的 provider 类型：{kind}") from exc

    @staticmethod
    def _normalize_name(name: str) -> str:
        """校验 provider 名称，统一去除首尾空格。"""
        normalized = name.strip()
        if not normalized:
            raise ValueError("provider 名称不能为空")
        return normalized

    @classmethod
    def _is_compatible(cls, kind: ProviderKind, provider: object) -> bool:
        """检查实现是否至少具备该能力契约要求的方法。"""
        return all(
            callable(getattr(provider, method_name, None))
            for method_name in cls._REQUIRED_METHODS[kind]
        )


__all__ = [
    "ProviderAlreadyRegisteredError",
    "ProviderImplementation",
    "ProviderKind",
    "ProviderKindError",
    "ProviderNotFoundError",
    "ProviderRegistration",
    "ProviderRegistry",
    "ProviderRegistryError",
]
