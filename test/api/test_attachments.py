"""附件 API 边界测试。"""

from fastapi.testclient import TestClient

from app.main import app


def test_upload_rejects_unsupported_extension() -> None:
    """不允许上传扩展名不在白名单内的文件。"""
    client = TestClient(app)
    response = client.post(
        "/api/v1/documents/00000000-0000-0000-0000-000000000001/attachments",
        files={"file": ("malware.exe", b"bad", "application/octet-stream")},
    )
    assert response.status_code == 422
