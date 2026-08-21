"""演示 FileStorage 契约、本地适配器和对象键安全校验。"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from 交付物.文件存储.local_storage import LocalFileStorage  # noqa: E402
from 交付物.文件存储.storage import build_object_key  # noqa: E402


def main() -> None:
    demo_root = PROJECT_ROOT / "交付物" / "运行日志" / "storage-demo"
    storage = LocalFileStorage(demo_root)
    object_key = build_object_key(
        document_id=UUID("33333333-3333-4333-8333-333333333333"),
        document_version_id=UUID("44444444-4444-4444-8444-444444444444"),
        attachment_id=UUID("55555555-5555-4555-8555-555555555555"),
        file_name="receipt-demo.txt",
    )
    stored = storage.put(object_key, b"redacted demo attachment\n", "text/plain")
    assert storage.get(object_key) == b"redacted demo attachment\n"
    assert storage.exists(object_key)
    storage.delete(object_key)
    assert not storage.exists(object_key)
    try:
        storage.put("../../outside.txt", b"blocked", "text/plain")
    except ValueError as exc:
        print(f"path_traversal=blocked ({exc})")
    else:
        raise AssertionError("目录穿越对象键未被拒绝")
    print(f"object_key={stored.object_key}")
    print(f"size={stored.size}")
    print("storage_demo=ok")


if __name__ == "__main__":
    main()
