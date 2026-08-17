"""附件查询、删除和解析接口测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_missing_attachment_returns_404() -> None:
    """不存在的附件不能被查询或解析。"""
    client = TestClient(app)
    path = f"/api/v1/documents/{uuid4()}/attachments/{uuid4()}"
    assert client.get(path).status_code == 404
    assert client.post(f"{path}/parse").status_code == 404
