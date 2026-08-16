"""FileStorage 安全约束测试。"""

from pathlib import Path

import pytest

from engines.common.local_storage import LocalFileStorage


def test_local_storage_round_trip_and_safe_url(tmp_path: Path) -> None:
    """对象键可读写且预签名有效期不超过五分钟。"""
    storage = LocalFileStorage(tmp_path)
    result = storage.put("documents/a.txt", b"hello", "text/plain")
    assert result.object_key == "documents/a.txt"
    assert storage.get(result.object_key) == b"hello"
    assert "S:" not in storage.create_presigned_url(result.object_key)
    with pytest.raises(ValueError):
        storage.create_presigned_url(result.object_key, 301)


def test_storage_rejects_path_traversal(tmp_path: Path) -> None:
    """对象键不能访问存储根目录外的文件。"""
    storage = LocalFileStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.put("../secret.txt", b"secret", "text/plain")
