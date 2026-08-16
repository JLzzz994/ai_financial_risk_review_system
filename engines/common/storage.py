"""文件对象存储抽象，业务代码不得依赖具体厂商 SDK。"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredObject:
    """对象存储返回的安全元数据。"""

    object_key: str
    size: int
    content_type: str


class FileStorage(Protocol):
    """本地和 MinIO 适配器共同实现的文件契约。"""

    def put(self, object_key: str, content: bytes, content_type: str) -> StoredObject:
        """写入对象并返回对象键，不返回本地绝对路径。"""

    def get(self, object_key: str) -> bytes:
        """读取对象内容。"""

    def delete(self, object_key: str) -> None:
        """删除对象。"""

    def create_presigned_url(self, object_key: str, expires_seconds: int = 300) -> str:
        """创建不超过五分钟的临时访问地址。"""


def validate_object_key(object_key: str) -> str:
    """拒绝绝对路径和目录穿越，返回规范化对象键。"""
    path = Path(object_key)
    if path.is_absolute() or ".." in path.parts or not object_key.strip():
        raise ValueError("对象键必须是相对路径")
    return object_key.replace("\\", "/")
