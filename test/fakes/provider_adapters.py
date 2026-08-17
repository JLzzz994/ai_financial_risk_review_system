"""ProviderRegistry 测试用的确定性 Fake Adapter。"""

from collections.abc import Iterable

from engines.common.storage import StoredObject, validate_object_key
from engines.model.contracts import (
    EmbeddingRequest,
    EmbeddingResult,
    ExtractionResult,
)
from engines.ocr.contracts import OcrRequest, OcrResult


class FakeOcrAdapter:
    """返回固定 OCR 结果，不访问外部服务。"""

    def __init__(self, result: OcrResult) -> None:
        """保存固定结果。"""
        self.result = result

    async def recognize(self, request: OcrRequest) -> OcrResult:
        """返回固定 OCR 结果，并校验请求附件一致。"""
        if request.attachment_id != self.result.attachment_id:
            raise ValueError("Fake OCR 请求附件与固定结果不一致")
        return self.result


class FakeLlmAdapter:
    """返回固定字段抽取结果，不调用模型服务。"""

    def __init__(self, result: ExtractionResult) -> None:
        """保存固定结果。"""
        self.result = result

    async def extract(self, text: str, prompt_version: str) -> ExtractionResult:
        """返回固定抽取结果，并校验提示词版本。"""
        del text
        if prompt_version != self.result.prompt_version:
            raise ValueError("Fake LLM 提示词版本与固定结果不一致")
        return self.result


class FakeEmbeddingAdapter:
    """返回固定向量结果，不调用 Embedding 服务。"""

    def __init__(self, result: EmbeddingResult) -> None:
        """保存固定结果。"""
        self.result = result

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        """返回固定向量，输入文本只用于保持接口形状。"""
        if not request.text.strip():
            raise ValueError("Embedding 文本不能为空")
        return self.result


class FakeRagAdapter:
    """返回固定制度证据列表，不访问向量数据库。"""

    def __init__(self, evidence: Iterable[str]) -> None:
        """保存不可变证据快照。"""
        self.evidence = tuple(evidence)

    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        """按 top_k 返回固定证据。"""
        if not query.strip():
            raise ValueError("RAG 查询不能为空")
        return list(self.evidence[:top_k])


class FakeFileStorage:
    """内存对象存储，仅用于测试 FileStorage 依赖。"""

    def __init__(self) -> None:
        """创建空对象空间。"""
        self._objects: dict[str, bytes] = {}

    def put(self, object_key: str, content: bytes, content_type: str) -> StoredObject:
        """写入内存并返回对象元数据。"""
        key = validate_object_key(object_key)
        self._objects[key] = bytes(content)
        return StoredObject(key, len(content), content_type)

    def get(self, object_key: str) -> bytes:
        """读取内存对象。"""
        return self._objects[validate_object_key(object_key)]

    def delete(self, object_key: str) -> None:
        """删除内存对象。"""
        self._objects.pop(validate_object_key(object_key), None)

    def create_presigned_url(self, object_key: str, expires_seconds: int = 300) -> str:
        """生成确定性的测试访问地址。"""
        if not 1 <= expires_seconds <= 300:
            raise ValueError("预签名地址有效期必须在 1 到 300 秒之间")
        return f"fake://{validate_object_key(object_key)}?expires={expires_seconds}"
