"""应用外部能力组装点。"""

from app.config import settings
from engines.common.provider_registry import ProviderKind, ProviderRegistry
from engines.common.storage import FileStorage
from engines.model.rag.education_adapter import EducationKnowledgeRagAdapter
from engines.model.rag.embedding import HttpBgeM3Embedding
from engines.model.rag.milvus_gateway import MilvusGateway
from engines.model.rag.reranker import HttpBgeReranker
from engines.ocr.paddleocr_adapter import PaddleOCRAdapter


def build_provider_registry(storage: FileStorage) -> ProviderRegistry:
    """注册生产默认 FileStorage 与 PaddleOCR，业务层不直接依赖 SDK。"""
    registry = ProviderRegistry()
    registry.register(ProviderKind.FILE_STORAGE, "default", storage)
    model_dir = settings.ocr_model if settings.ocr_model not in {"", "default"} else None
    registry.register(
        ProviderKind.OCR,
        "paddleocr",
        PaddleOCRAdapter(storage, language="ch", model_dir=model_dir),
    )
    _register_rag_provider(registry)
    return registry


def build_rag_provider_registry() -> ProviderRegistry:
    """只组装 RAG provider，避免查询接口实例化 OCR 或对象存储。"""
    registry = ProviderRegistry()
    _register_rag_provider(registry)
    return registry


def _register_rag_provider(registry: ProviderRegistry) -> None:
    """按配置延迟组装教育知识库 RAG provider。"""
    if not settings.rag_enabled:
        return
    embedding = HttpBgeM3Embedding(
        settings.rag_embedding_base_url,
        api_key=settings.rag_embedding_api_key,
        timeout_seconds=settings.rag_embedding_timeout_seconds,
        model_version=settings.rag_embedding_model_version or None,
    )
    gateway = MilvusGateway(
        settings.milvus_uri,
        settings.milvus_collection,
        token=settings.milvus_token,
        timeout_seconds=settings.milvus_timeout_seconds,
        dense_weight=settings.rag_dense_weight,
        sparse_weight=settings.rag_sparse_weight,
    )
    reranker = (
        HttpBgeReranker(
            settings.rag_reranker_base_url,
            api_key=settings.rag_reranker_api_key,
            timeout_seconds=settings.rag_reranker_timeout_seconds,
        )
        if settings.rag_reranker_enabled
        else None
    )
    registry.register(
        ProviderKind.RAG,
        "education-kb",
        EducationKnowledgeRagAdapter(
            embedding=embedding,
            gateway=gateway,
            reranker=reranker,
            rule_version=settings.rag_rule_version,
        ),
    )


__all__ = ["build_provider_registry", "build_rag_provider_registry"]
