"""开发环境本地文件存储适配器。"""

from pathlib import Path

from engines.common.storage import StoredObject, validate_object_key


class LocalFileStorage:
    """仅开发环境使用的本地存储，数据库只记录 object_key。"""

    def __init__(self, root: Path) -> None:
        """初始化存储根目录。"""
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, object_key: str, content: bytes, content_type: str) -> StoredObject:
        """写入对象并阻止路径逃逸。"""
        key = validate_object_key(object_key)
        target = (self.root / key).resolve()
        if self.root not in target.parents:
            raise ValueError("对象键超出存储根目录")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return StoredObject(key, len(content), content_type)

    def get(self, object_key: str) -> bytes:
        """读取对象。"""
        key = validate_object_key(object_key)
        target = (self.root / key).resolve()
        if self.root not in target.parents:
            raise ValueError("对象键超出存储根目录")
        return target.read_bytes()

    def delete(self, object_key: str) -> None:
        """删除对象。"""
        key = validate_object_key(object_key)
        target = (self.root / key).resolve()
        if self.root not in target.parents:
            raise ValueError("对象键超出存储根目录")
        if target.exists():
            target.unlink()

    def create_presigned_url(self, object_key: str, expires_seconds: int = 300) -> str:
        """开发环境返回受限的内部对象地址，不泄露绝对路径。"""
        if not 1 <= expires_seconds <= 300:
            raise ValueError("预签名地址有效期必须在 1 到 300 秒之间")
        return f"/api/v1/objects/{validate_object_key(object_key)}?expires={expires_seconds}"
