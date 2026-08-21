"""RAG 适配器的可识别错误。"""


class RagError(Exception):
    """RAG 适配器异常基类。"""

    code = "rag_error"


class RagNotConfiguredError(RagError):
    """RAG 未启用或缺少必要配置。"""

    code = "rag_not_configured"


class RagDependencyMissingError(RagError):
    """可选 RAG SDK 未安装。"""

    code = "rag_dependency_missing"


class RagUnavailableError(RagError):
    """Milvus 或外部模型服务不可访问。"""

    code = "rag_unavailable"


class RagQueryError(RagError):
    """查询参数或下游响应无效。"""

    code = "rag_query_failed"
