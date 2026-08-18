"""MinIO 适配器契约；业务层不依赖 MinIO SDK 类型。"""

from collections.abc import Callable
from importlib import import_module
from io import BytesIO
from typing import cast

from engines.common.storage import StoredObject


class MinioFileStorage:
    """对 MinIO 客户端能力的窄接口适配器。"""

    def __init__(
        self,
        putter: Callable[[str, bytes, str], StoredObject],
        *,
        getter: Callable[[str], bytes] | None = None,
        deleter: Callable[[str], None] | None = None,
        presigner: Callable[[str, int], str] | None = None,
    ) -> None:
        """注入已配置超时、加密和审计的对象存储窄回调。"""
        self._putter = putter
        self._getter = getter
        self._deleter = deleter
        self._presigner = presigner

    @classmethod
    def from_settings(
        cls,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ) -> "MinioFileStorage":
        """使用环境配置创建 MinIO SDK 回调，业务服务仍只依赖 FileStorage。"""
        try:
            module = import_module("minio")
        except ImportError as exc:
            raise RuntimeError("MinIO 适配器依赖未安装") from exc
        client = module.Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)

        def putter(object_key: str, content: bytes, content_type: str) -> StoredObject:
            client.put_object(
                bucket,
                object_key,
                BytesIO(content),
                len(content),
                content_type=content_type,
            )
            return StoredObject(object_key, len(content), content_type)

        def getter(object_key: str) -> bytes:
            response = client.get_object(bucket, object_key)
            try:
                return cast(bytes, response.read())
            finally:
                response.close()
                response.release_conn()

        def deleter(object_key: str) -> None:
            client.remove_object(bucket, object_key)

        def presigner(object_key: str, expires_seconds: int) -> str:
            from datetime import timedelta

            return cast(str, client.presigned_get_object(
                bucket,
                object_key,
                expires=timedelta(seconds=expires_seconds),
            ))

        return cls.with_callbacks(
            putter,
            getter=getter,
            deleter=deleter,
            presigner=presigner,
        )

    @classmethod
    def with_callbacks(
        cls,
        putter: Callable[[str, bytes, str], StoredObject],
        *,
        getter: Callable[[str], bytes],
        deleter: Callable[[str], None],
        presigner: Callable[[str, int], str],
    ) -> "MinioFileStorage":
        """通过回调组装完整适配器，业务代码无需导入 MinIO SDK。"""
        return cls(putter, getter=getter, deleter=deleter, presigner=presigner)

    def put(self, object_key: str, content: bytes, content_type: str) -> StoredObject:
        """委托对象写入，不在业务层暴露 MinIO 类型。"""
        return self._putter(object_key, content, content_type)

    def get(self, object_key: str) -> bytes:
        """委托对象读取。"""
        if self._getter is None:
            raise RuntimeError("MinIO 读取回调未配置")
        return self._getter(object_key)

    def delete(self, object_key: str) -> None:
        """委托对象删除。"""
        if self._deleter is None:
            raise RuntimeError("MinIO 删除回调未配置")
        self._deleter(object_key)

    def create_presigned_url(self, object_key: str, expires_seconds: int = 300) -> str:
        """委托生成短期预签名地址，并限制最长五分钟。"""
        if not 1 <= expires_seconds <= 300:
            raise ValueError("预签名地址有效期必须在 1 到 300 秒之间")
        if self._presigner is None:
            raise RuntimeError("MinIO 预签名回调未配置")
        return self._presigner(object_key, expires_seconds)
