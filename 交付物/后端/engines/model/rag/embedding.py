"""外部 BGE-M3 稠密/稀疏向量 HTTP 适配器。"""

from collections.abc import Mapping, Sequence
from typing import Any, cast

from engines.model.rag.errors import (
    RagDependencyMissingError,
    RagNotConfiguredError,
    RagQueryError,
    RagUnavailableError,
)


class HybridEmbeddingResult:
    """一次查询的混合向量。"""

    __slots__ = ("dense", "sparse", "model_version")

    def __init__(
        self,
        dense: tuple[float, ...],
        sparse: dict[int, float],
        model_version: str,
    ) -> None:
        self.dense = dense
        self.sparse = sparse
        self.model_version = model_version


def sparse_row_to_dict(row: object) -> dict[int, float]:
    """将 scipy/numpy 风格稀疏行转成 Milvus 可接受的字典。"""
    indices = getattr(row, "indices", None)
    data = getattr(row, "data", None)
    if indices is None or data is None:
        if isinstance(row, Mapping):
            return {int(key): float(value) for key, value in row.items()}
        raise RagQueryError("BGE-M3 稀疏向量格式无效")
    return {int(index): float(value) for index, value in zip(indices, data, strict=True)}


def _new_http_client(*, timeout: float, headers: dict[str, str]) -> Any:
    """延迟创建 HTTP 客户端，确保 RAG 关闭时不要求导入 httpx。"""

    try:
        import httpx
    except ImportError as exc:
        raise RagDependencyMissingError(
            "RAG HTTP 依赖未安装，请安装 requirements-rag.txt"
        ) from exc
    return httpx.Client(timeout=timeout, headers=headers)


class HttpBgeM3Embedding:
    """调用外部 BGE-M3 服务生成一条混合向量。"""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str = "",
        timeout_seconds: int = 60,
        model_version: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.model_version = model_version or "external-bge-m3"

    def embed(self, text: str) -> HybridEmbeddingResult:
        """同步请求向量；调用方应在线程池中执行，避免阻塞事件循环。"""
        if not text.strip():
            raise RagQueryError("查询文本不能为空")
        if not self.base_url:
            raise RagNotConfiguredError("未配置外部 BGE-M3 服务地址")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            with _new_http_client(timeout=self.timeout_seconds, headers=headers) as client:
                response = client.post(
                    f"{self.base_url}/embed",
                    json={"texts": [text]},
                    headers=headers,
                )
        except RagDependencyMissingError:
            raise
        except Exception as exc:
            raise RagUnavailableError("外部 BGE-M3 服务不可用") from exc
        if getattr(response, "status_code", 500) >= 400:
            raise RagUnavailableError("外部 BGE-M3 服务返回错误")
        try:
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise RagQueryError("BGE-M3 服务响应格式无效")
            payload_data = payload.get("data", payload)
            if not isinstance(payload_data, Mapping):
                raise RagQueryError("BGE-M3 服务响应格式无效")
            dense_rows = payload_data.get("dense")
            sparse_rows = payload_data.get("sparse")
            if not isinstance(dense_rows, Sequence) or not dense_rows:
                raise RagQueryError("BGE-M3 稠密向量格式无效")
            if not isinstance(sparse_rows, Sequence) or not sparse_rows:
                raise RagQueryError("BGE-M3 稀疏向量格式无效")
            dense_values = dense_rows[0]
            sparse_values = sparse_rows[0]
            dense = tuple(
                float(cast(Any, value)) for value in _to_sequence(dense_values)
            )
            sparse = sparse_row_to_dict(sparse_values)
            response_model_version = payload_data.get("model_version")
            model_version = (
                response_model_version
                if isinstance(response_model_version, str) and response_model_version
                else self.model_version
            )
        except RagQueryError:
            raise
        except Exception as exc:
            raise RagQueryError("BGE-M3 向量生成失败") from exc
        if not dense:
            raise RagQueryError("BGE-M3 稠密向量不能为空")
        return HybridEmbeddingResult(dense, sparse, model_version)


def _to_sequence(values: object) -> Sequence[object]:
    """将 numpy 数组或普通序列转换为可迭代序列。"""
    to_list = getattr(values, "tolist", None)
    if callable(to_list):
        converted = to_list()
        if isinstance(converted, Sequence):
            return converted
    if isinstance(values, Sequence):
        return values
    raise RagQueryError("BGE-M3 稠密向量格式无效")


__all__ = ["HttpBgeM3Embedding", "HybridEmbeddingResult", "sparse_row_to_dict"]
