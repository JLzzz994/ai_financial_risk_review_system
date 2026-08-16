"""审核会话 API 测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_create_review_session() -> None:
    """会话必须绑定单据版本。"""
    client = TestClient(app)
    response = client.post(f"/api/v1/review-sessions?document_version_id={uuid4()}")
    assert response.status_code == 200
    assert response.json()["status"] == "open"
