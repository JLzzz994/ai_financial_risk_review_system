"""附件上传、版本绑定、访问控制和解析状态服务。"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from engines.common.storage import FileStorage, StoredObject, build_object_key
from engines.security.file_validator import MAX_ATTACHMENT_SIZE, FileValidationError, validate_file
from engines.security.virus_scanner import CleanVirusScanner, VirusScanner, VirusScanStatus


class AttachmentPermissionError(PermissionError):
    """当前主体无权访问或修改附件。"""


class AttachmentStateError(ValueError):
    """附件或单据版本当前状态不允许执行操作。"""


@dataclass(frozen=True, slots=True)
class AttachmentUpload:
    """兼容旧接口的附件上传结果。"""

    object_key: str
    size: int
    content_type: str
    parse_status: str = "pending"


@dataclass(slots=True)
class AttachmentRecord:
    """附件元数据，不保存本地绝对路径或附件正文。"""

    attachment_id: UUID
    document_id: UUID
    document_version_id: UUID
    file_name: str
    file_size: int
    mime_type: str
    object_key: str
    file_hash: str
    uploaded_by: UUID
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    required_kind: str | None = None
    storage_status: str = "stored"
    parse_status: str = "pending"
    retry_count: int = 0
    parse_error: str | None = None
    storage_error: str | None = None


class InMemoryAttachmentRepository:
    """开发阶段附件元数据仓储，接口与后续 PostgreSQL Repository 对齐。"""

    def __init__(self) -> None:
        """初始化空仓储。"""
        self._records: dict[UUID, AttachmentRecord] = {}

    def save(self, record: AttachmentRecord) -> AttachmentRecord:
        """保存或更新附件元数据。"""
        self._records[record.attachment_id] = record
        return record

    def get(self, attachment_id: UUID) -> AttachmentRecord | None:
        """按附件 ID 获取元数据。"""
        return self._records.get(attachment_id)

    def find_by_hash(self, document_version_id: UUID, file_hash: str) -> AttachmentRecord | None:
        """按版本和 SHA-256 查找去重记录，忽略已删除元数据。"""
        return next(
            (
                record
                for record in self._records.values()
                if record.document_version_id == document_version_id
                and record.file_hash == file_hash
                and record.storage_status != "deleted"
            ),
            None,
        )

    def list_by_document(self, document_id: UUID) -> list[AttachmentRecord]:
        """查询单据全部未删除附件。"""
        return [
            record
            for record in self._records.values()
            if record.document_id == document_id and record.storage_status != "deleted"
        ]

    def list_by_version(self, document_version_id: UUID) -> list[AttachmentRecord]:
        """查询版本全部未删除附件。"""
        return [
            record
            for record in self._records.values()
            if record.document_version_id == document_version_id
            and record.storage_status != "deleted"
        ]


class AttachmentService:
    """通过 FileStorage 管理附件，不依赖具体对象存储 SDK。"""

    allowed_extensions = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".xls", ".docx"})
    max_file_size = MAX_ATTACHMENT_SIZE
    max_version_size = 200 * 1024 * 1024
    editable_document_statuses = frozenset({"draft", "withdrawn", "returned"})

    def __init__(
        self,
        storage: FileStorage,
        repository: InMemoryAttachmentRepository | None = None,
        scanner: VirusScanner | None = None,
        access_checker: Callable[[AttachmentRecord, UUID], bool] | None = None,
    ) -> None:
        """注入对象存储、元数据仓储、扫描器和可选数据权限检查器。"""
        self.storage = storage
        self.repository = repository or InMemoryAttachmentRepository()
        self.scanner = scanner or CleanVirusScanner()
        self.access_checker = access_checker

    def upload(
        self, object_key: str, content: bytes, content_type: str, extension: str
    ) -> AttachmentUpload:
        """兼容早期调用方的上传方法，严格版本绑定入口使用 upload_attachment。"""
        if len(content) > self.max_file_size:
            raise ValueError("单个附件不能超过 20MB")
        if extension.lower() not in self.allowed_extensions:
            raise ValueError("附件扩展名不在白名单中")
        stored: StoredObject = self.storage.put(object_key, content, content_type)
        return AttachmentUpload(stored.object_key, stored.size, stored.content_type)

    def upload_attachment(
        self,
        *,
        document_id: UUID,
        document_version_id: UUID,
        file_name: str,
        content: bytes,
        content_type: str,
        actor_id: UUID,
        document_status: str,
        required_kind: str | None = None,
    ) -> AttachmentRecord:
        """校验、扫描并保存绑定不可变版本的附件。"""
        if document_status not in self.editable_document_statuses:
            raise AttachmentStateError("当前单据版本不允许新增附件")
        validate_file(file_name, content, content_type, max_size=self.max_file_size)
        file_hash = sha256(content).hexdigest()
        duplicate = self.repository.find_by_hash(document_version_id, file_hash)
        if duplicate is not None:
            return duplicate
        current_size = sum(
            record.file_size for record in self.repository.list_by_version(document_version_id)
        )
        if current_size + len(content) > self.max_version_size:
            raise FileValidationError("单据版本附件总量不能超过 200MB")

        scan_result = self.scanner.scan(content)
        if scan_result.status is not VirusScanStatus.CLEAN:
            message = scan_result.message or "病毒扫描未通过"
            raise FileValidationError(f"病毒扫描未通过：{message}")

        attachment_id = uuid4()
        object_key = build_object_key(document_id, document_version_id, attachment_id, file_name)
        try:
            stored = self.storage.put(object_key, content, content_type)
        except Exception as exc:
            raise FileValidationError("附件对象保存失败") from exc
        record = AttachmentRecord(
            attachment_id=attachment_id,
            document_id=document_id,
            document_version_id=document_version_id,
            file_name=Path(file_name).name,
            file_size=stored.size,
            mime_type=stored.content_type,
            object_key=stored.object_key,
            file_hash=file_hash,
            uploaded_by=actor_id,
            required_kind=required_kind,
        )
        try:
            return self.repository.save(record)
        except Exception:
            self.storage.delete(object_key)
            raise

    def list_attachments(self, document_id: UUID) -> list[AttachmentRecord]:
        """列出单据附件元数据。"""
        return self.repository.list_by_document(document_id)

    def get_attachment(
        self, attachment_id: UUID, *, actor_id: UUID | None = None
    ) -> AttachmentRecord:
        """查询附件并执行可选数据范围校验。"""
        record = self.repository.get(attachment_id)
        if record is None or record.storage_status == "deleted":
            raise KeyError("附件不存在")
        self._assert_access(record, actor_id)
        return record

    def create_download_url(
        self, attachment_id: UUID, *, actor_id: UUID | None = None, expires_seconds: int = 300
    ) -> str:
        """校验权限后生成不超过五分钟的短期下载地址。"""
        record = self.get_attachment(attachment_id, actor_id=actor_id)
        return self.storage.create_presigned_url(record.object_key, expires_seconds)

    def read_content(self, attachment_id: UUID, *, actor_id: UUID | None = None) -> bytes:
        """校验权限后读取对象内容，调用方不得把正文写入日志。"""
        record = self.get_attachment(attachment_id, actor_id=actor_id)
        return self.storage.get(record.object_key)

    def delete_attachment(
        self, attachment_id: UUID, *, actor_id: UUID, document_status: str
    ) -> AttachmentRecord:
        """删除草稿/退回版本附件；已提交版本只允许通过新版本替换。"""
        record = self.get_attachment(attachment_id, actor_id=actor_id)
        if record.uploaded_by != actor_id:
            raise AttachmentPermissionError("只有附件上传人可以删除附件")
        if document_status not in self.editable_document_statuses:
            raise AttachmentStateError("已提交版本附件不可删除")
        record.storage_status = "deleted"
        try:
            self.storage.delete(record.object_key)
        except Exception as exc:
            record.storage_status = "failed"
            record.storage_error = "对象删除失败，可稍后重试"
            self.repository.save(record)
            raise FileValidationError(record.storage_error) from exc
        return self.repository.save(record)

    def mark_parse_running(self, attachment_id: UUID) -> AttachmentRecord:
        """将附件解析状态推进到 parsing。"""
        record = self.get_attachment(attachment_id)
        if record.storage_status != "stored":
            raise AttachmentStateError("对象未处于 stored 状态，不能解析")
        record.parse_status = "parsing"
        record.parse_error = None
        return self.repository.save(record)

    def mark_parse_succeeded(self, attachment_id: UUID) -> AttachmentRecord:
        """保存解析成功状态；结果实体由解析仓储另行追加。"""
        record = self.get_attachment(attachment_id)
        record.parse_status = "succeeded"
        record.parse_error = None
        return self.repository.save(record)

    def mark_parse_failed(self, attachment_id: UUID, error_message: str) -> AttachmentRecord:
        """记录解析失败，保留脱敏错误信息以便重试和人工接管。"""
        record = self.get_attachment(attachment_id)
        record.parse_status = "failed"
        record.parse_error = error_message[:500]
        return self.repository.save(record)

    def retry_parse(self, attachment_id: UUID, *, attempt: int) -> AttachmentRecord:
        """按最多三次自动重试策略恢复解析，超过上限进入人工接管。"""
        record = self.get_attachment(attachment_id)
        if attempt < 1:
            raise ValueError("解析尝试次数必须从 1 开始")
        record.retry_count = attempt
        if attempt > 3:
            record.parse_status = "manual_review"
            return self.repository.save(record)
        record.parse_status = "pending"
        return self.repository.save(record)

    def assert_parseable(self, virus_scan_passed: bool) -> None:
        """病毒扫描未通过时禁止进入解析流程。"""
        if not virus_scan_passed:
            raise ValueError("病毒扫描未通过，禁止解析")

    def _assert_access(self, record: AttachmentRecord, actor_id: UUID | None) -> None:
        """执行附件主体权限检查；组织范围由上层 checker 注入。"""
        if actor_id is None:
            return
        if self.access_checker is not None and not self.access_checker(record, actor_id):
            raise AttachmentPermissionError("无权访问该附件")


__all__ = [
    "AttachmentPermissionError",
    "AttachmentRecord",
    "AttachmentService",
    "AttachmentStateError",
    "AttachmentUpload",
    "InMemoryAttachmentRepository",
]
