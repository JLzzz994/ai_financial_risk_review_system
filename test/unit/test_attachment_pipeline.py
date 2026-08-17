"""附件与解析基础链路测试。"""

from pathlib import Path
from uuid import uuid4

import pytest

from app.services.attachment_service import (
    AttachmentPermissionError,
    AttachmentService,
    AttachmentStateError,
    InMemoryAttachmentRepository,
)
from engines.common.local_storage import LocalFileStorage
from engines.common.minio_storage import MinioFileStorage
from engines.common.storage import StoredObject
from engines.security.file_validator import FileValidationError
from engines.security.virus_scanner import VirusScanResult, VirusScanStatus


def _pdf() -> bytes:
    """返回最小 PDF 文件头样本。"""
    return b"%PDF-1.7\nfinancial sample"


def test_upload_binds_version_and_deduplicates_by_sha256(tmp_path: Path) -> None:
    """同一版本相同文件只创建一条附件记录并复用对象。"""
    repository = InMemoryAttachmentRepository()
    service = AttachmentService(LocalFileStorage(tmp_path), repository)
    document_id = uuid4()
    version_id = uuid4()
    actor_id = uuid4()

    first = service.upload_attachment(
        document_id=document_id,
        document_version_id=version_id,
        file_name="发票.pdf",
        content=_pdf(),
        content_type="application/pdf",
        actor_id=actor_id,
        document_status="draft",
    )
    duplicate = service.upload_attachment(
        document_id=document_id,
        document_version_id=version_id,
        file_name="另一名称.pdf",
        content=_pdf(),
        content_type="application/pdf",
        actor_id=actor_id,
        document_status="draft",
    )

    assert duplicate.attachment_id == first.attachment_id
    assert duplicate.document_version_id == version_id
    assert len(repository.list_by_version(version_id)) == 1
    assert first.file_hash


def test_upload_rejects_mismatched_content_header(tmp_path: Path) -> None:
    """扩展名、MIME 和文件头不一致时禁止保存对象。"""
    service = AttachmentService(LocalFileStorage(tmp_path))
    with pytest.raises(FileValidationError):
        service.upload_attachment(
            document_id=uuid4(),
            document_version_id=uuid4(),
            file_name="not-pdf.pdf",
            content=b"not a pdf",
            content_type="application/pdf",
            actor_id=uuid4(),
            document_status="draft",
        )


def test_upload_rejects_infected_file_without_storing(tmp_path: Path) -> None:
    """病毒扫描未通过时不写入正式对象，也不进入解析。"""
    class InfectedScanner:
        """测试用病毒扫描器。"""

        def scan(self, content: bytes) -> VirusScanResult:
            del content
            return VirusScanResult(VirusScanStatus.INFECTED, "命中测试签名")

    service = AttachmentService(LocalFileStorage(tmp_path), scanner=InfectedScanner())
    with pytest.raises(FileValidationError, match="病毒扫描"):
        service.upload_attachment(
            document_id=uuid4(),
            document_version_id=uuid4(),
            file_name="invoice.pdf",
            content=_pdf(),
            content_type="application/pdf",
            actor_id=uuid4(),
            document_status="draft",
        )
    assert not list(tmp_path.rglob("*"))


def test_delete_requires_owner_and_editable_version(tmp_path: Path) -> None:
    """非上传人或已提交版本不能删除附件。"""
    service = AttachmentService(LocalFileStorage(tmp_path))
    owner = uuid4()
    record = service.upload_attachment(
        document_id=uuid4(),
        document_version_id=uuid4(),
        file_name="invoice.pdf",
        content=_pdf(),
        content_type="application/pdf",
        actor_id=owner,
        document_status="draft",
    )
    with pytest.raises(AttachmentPermissionError):
        service.delete_attachment(record.attachment_id, actor_id=uuid4(), document_status="draft")
    with pytest.raises(AttachmentStateError):
        service.delete_attachment(
            record.attachment_id, actor_id=owner, document_status="pending_review"
        )
    deleted = service.delete_attachment(
        record.attachment_id, actor_id=owner, document_status="draft"
    )
    assert deleted.storage_status == "deleted"


def test_parse_retry_enters_manual_review_after_three_attempts(tmp_path: Path) -> None:
    """解析失败最多自动重试三次，超限后进入人工接管。"""
    service = AttachmentService(LocalFileStorage(tmp_path))
    record = service.upload_attachment(
        document_id=uuid4(),
        document_version_id=uuid4(),
        file_name="invoice.pdf",
        content=_pdf(),
        content_type="application/pdf",
        actor_id=uuid4(),
        document_status="draft",
    )
    assert service.mark_parse_running(record.attachment_id).parse_status == "parsing"
    failed = service.mark_parse_failed(record.attachment_id, "OCR 超时")
    assert failed.parse_status == "failed"
    manual = service.retry_parse(record.attachment_id, attempt=4)
    assert manual.parse_status == "manual_review"
    assert manual.parse_error == "OCR 超时"


def test_minio_adapter_uses_narrow_callbacks() -> None:
    """MinIO 适配器只通过注入的窄回调工作，不依赖 SDK 类型。"""
    calls: list[str] = []

    def putter(key: str, content: bytes, content_type: str) -> StoredObject:
        calls.append(f"put:{key}")
        return StoredObject(key, len(content), content_type)

    adapter = MinioFileStorage(
        putter,
        getter=lambda key: (calls.append(f"get:{key}") or b"ok"),
        deleter=lambda key: calls.append(f"delete:{key}"),
        presigner=lambda key, expires: f"minio://{key}?expires={expires}",
    )
    assert adapter.put("a.pdf", b"x", "application/pdf").size == 1
    assert adapter.get("a.pdf") == b"ok"
    adapter.delete("a.pdf")
    assert adapter.create_presigned_url("a.pdf", 60).endswith("expires=60")
    assert calls == ["put:a.pdf", "get:a.pdf", "delete:a.pdf"]
