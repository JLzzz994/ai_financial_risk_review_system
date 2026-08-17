"""ProviderRegistry 和 ActionRegistry 的白名单行为测试。"""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from engines.common.action_registry import (
    ActionAlreadyRegisteredError,
    ActionCategory,
    ActionDefinition,
    ActionNotAllowedError,
    ActionRegistry,
)
from engines.common.provider_registry import (
    ProviderAlreadyRegisteredError,
    ProviderKind,
    ProviderNotFoundError,
    ProviderRegistry,
)
from engines.common.storage import StoredObject
from engines.model.contracts import (
    EmbeddingRequest,
    EmbeddingResult,
    ExtractionResult,
)
from engines.ocr.contracts import OcrRequest, OcrResult
from test.fakes.provider_adapters import (
    FakeEmbeddingAdapter,
    FakeFileStorage,
    FakeLlmAdapter,
    FakeOcrAdapter,
    FakeRagAdapter,
)


@dataclass(frozen=True, slots=True)
class _FakeQueryAction:
    """用于验证注册中心返回领域动作定义的测试动作。"""

    value: str


def _fake_handler() -> _FakeQueryAction:
    """返回一个确定性的查询结果。"""
    return _FakeQueryAction("ok")


def test_register_and_get_each_provider_by_kind_and_name() -> None:
    """五类适配器均可以按类型和名称注册、查询。"""
    attachment_id = uuid4()
    ocr = FakeOcrAdapter(
        OcrResult(attachment_id=attachment_id, text="文本", page_count=1, confidence=0.99)
    )
    llm = FakeLlmAdapter(
        ExtractionResult(fields={"amount": "10.00"}, confidence=1.0, prompt_version="p1")
    )
    embedding = FakeEmbeddingAdapter(EmbeddingResult(vector=(0.1, 0.2), model_version="e1"))
    rag = FakeRagAdapter(("制度证据",))
    storage = FakeFileStorage()
    registry = ProviderRegistry()

    registry.register(ProviderKind.OCR, "fake-ocr", ocr)
    registry.register(ProviderKind.LLM, "fake-llm", llm)
    registry.register(ProviderKind.EMBEDDING, "fake-embedding", embedding)
    registry.register(ProviderKind.RAG, "fake-rag", rag)
    registry.register(ProviderKind.FILE_STORAGE, "fake-storage", storage)

    assert registry.get(ProviderKind.OCR, "fake-ocr") is ocr
    assert registry.get(ProviderKind.LLM, "fake-llm") is llm
    assert registry.get(ProviderKind.EMBEDDING, "fake-embedding") is embedding
    assert registry.get(ProviderKind.RAG, "fake-rag") is rag
    assert registry.get(ProviderKind.FILE_STORAGE, "fake-storage") is storage


def test_duplicate_provider_registration_is_rejected() -> None:
    """同一类型下重复使用名称必须明确拒绝。"""
    registry = ProviderRegistry()
    registry.register(ProviderKind.RAG, "fake-rag", FakeRagAdapter(("证据",)))

    with pytest.raises(ProviderAlreadyRegisteredError, match="fake-rag"):
        registry.register(ProviderKind.RAG, "fake-rag", FakeRagAdapter(("另一条证据",)))


def test_missing_provider_is_rejected() -> None:
    """查询未注册适配器必须返回明确的缺失异常。"""
    with pytest.raises(ProviderNotFoundError, match="fake-ocr"):
        ProviderRegistry().get(ProviderKind.OCR, "fake-ocr")


def test_provider_kind_rejects_incompatible_adapter() -> None:
    """适配器实现与注册类型不匹配时不能进入注册中心。"""
    registry = ProviderRegistry()

    with pytest.raises(TypeError, match="不兼容"):
        registry.register(ProviderKind.OCR, "not-ocr", FakeRagAdapter(("证据",)))


def test_action_registry_accepts_query_and_analysis_allowlist() -> None:
    """ActionRegistry 仅接受预定义的查询和分析动作。"""
    registry = ActionRegistry()
    query = ActionDefinition(name="supplier.query", handler=_fake_handler)
    analysis = ActionDefinition(name="risk.explain", handler=_fake_handler)

    registry.register(query)
    registry.register(analysis)

    assert registry.get("supplier.query").name == query.name
    assert registry.get("risk.explain").name == analysis.name
    assert registry.get("supplier.query").category == ActionCategory.QUERY
    assert registry.get("risk.explain").category == ActionCategory.ANALYSIS


def test_action_registry_rejects_non_allowlist_and_approval_actions() -> None:
    """非白名单动作（尤其审批决定）不能被 Agent 注册。"""
    registry = ActionRegistry()

    for action_name in ("unknown.action", "approval.decide", "approval.reject"):
        with pytest.raises(ActionNotAllowedError, match=action_name):
            registry.register(ActionDefinition(name=action_name, handler=_fake_handler))


def test_duplicate_action_registration_is_rejected() -> None:
    """同名动作重复注册必须明确拒绝，避免覆盖既有处理器。"""
    registry = ActionRegistry()
    action = ActionDefinition(name="document.query", handler=_fake_handler)
    registry.register(action)

    with pytest.raises(ActionAlreadyRegisteredError, match="document.query"):
        registry.register(action)


def test_fake_adapters_are_deterministic_and_satisfy_protocols() -> None:
    """Fake Adapter 返回固定结果，供自动化测试复用而不依赖外部服务。"""
    attachment_id = uuid4()
    request = OcrRequest(attachment_id=attachment_id, object_key="a.pdf")
    ocr = FakeOcrAdapter(OcrResult(attachment_id, "文本", 1, 1.0))
    llm = FakeLlmAdapter(ExtractionResult({"amount": "10.00"}, 1.0, "p1"))
    embedding = FakeEmbeddingAdapter(EmbeddingResult((0.1, 0.2), "e1"))
    rag = FakeRagAdapter(("证据",))
    storage = FakeFileStorage()

    import asyncio

    assert asyncio.run(ocr.recognize(request)).text == "文本"
    assert asyncio.run(ocr.recognize(request)).text == "文本"
    assert asyncio.run(llm.extract("文本", "p1")).fields == {"amount": "10.00"}
    assert asyncio.run(embedding.embed(EmbeddingRequest("文本"))).vector == (0.1, 0.2)
    assert asyncio.run(rag.retrieve("问题")) == ["证据"]
    stored = storage.put("a.txt", "内容".encode(), "text/plain")
    assert stored == StoredObject("a.txt", len("内容".encode()), "text/plain")
    assert storage.get("a.txt") == "内容".encode()
