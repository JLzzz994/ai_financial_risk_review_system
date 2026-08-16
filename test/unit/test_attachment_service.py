"""附件服务安全校验测试。"""

import pytest

from app.services.attachment_service import AttachmentService
from engines.common.local_storage import LocalFileStorage


def test_attachment_upload_limits_and_scan_gate(tmp_path) -> None:
    """验证大小、扩展名和病毒扫描门禁。"""
    service = AttachmentService(LocalFileStorage(tmp_path))
    result = service.upload("documents/a.pdf", b"pdf", "application/pdf", ".pdf")
    assert result.parse_status == "pending"
    with pytest.raises(ValueError):
        service.upload("documents/a.exe", b"x", "application/octet-stream", ".exe")
    with pytest.raises(ValueError):
        service.assert_parseable(False)
