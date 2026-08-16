"""附件上传和解析前置校验。"""

from dataclasses import dataclass

from engines.common.storage import FileStorage, StoredObject


@dataclass(frozen=True, slots=True)
class AttachmentUpload:
    """附件上传结果。"""

    object_key: str
    size: int
    content_type: str
    parse_status: str = "pending"


class AttachmentService:
    """执行附件大小、扩展名和病毒扫描状态校验。"""

    allowed_extensions = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".docx"})
    max_file_size = 20 * 1024 * 1024

    def __init__(self, storage: FileStorage) -> None:
        """注入 FileStorage，不依赖具体存储厂商。"""
        self.storage = storage

    def upload(self, object_key: str, content: bytes, content_type: str, extension: str) -> AttachmentUpload:
        """校验并保存单个附件，病毒扫描由后续任务更新状态。"""
        if len(content) > self.max_file_size:
            raise ValueError("单个附件不能超过 20MB")
        if extension.lower() not in self.allowed_extensions:
            raise ValueError("附件扩展名不在白名单中")
        stored: StoredObject = self.storage.put(object_key, content, content_type)
        return AttachmentUpload(stored.object_key, stored.size, stored.content_type)

    def assert_parseable(self, virus_scan_passed: bool) -> None:
        """病毒扫描未通过时禁止进入解析流程。"""
        if not virus_scan_passed:
            raise ValueError("病毒扫描未通过，禁止解析")
