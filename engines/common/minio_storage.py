"""MinIO 适配器契约；实际 SDK 接入通过构造注入，业务层不依赖 SDK。"""

from collections.abc import Callable

from engines.common.storage import StoredObject


class MinioFileStorage:
    """对 MinIO 客户端能力的窄接口适配器。"""

    def __init__(self, putter: Callable[[str, bytes, str], StoredObject]) -> None:
        """注入已配置超时、加密和审计的对象写入函数。"""
        self._putter = putter

    def put(self, object_key: str, content: bytes, content_type: str) -> StoredObject:
        """委托对象写入，不在业务层暴露 MinIO 类型。"""
        return self._putter(object_key, content, content_type)
