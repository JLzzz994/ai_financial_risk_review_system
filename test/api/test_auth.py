"""认证 API 的安全失败行为测试。"""

from fastapi.testclient import TestClient

from app.main import app


def test_login_returns_service_unavailable_until_auth_is_configured() -> None:
    """未接入真实认证时不能返回伪造令牌。"""
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"username": "demo", "password": "secret"})
    assert response.status_code == 503


def test_me_requires_bearer_token() -> None:
    """未携带令牌时返回 401。"""
    client = TestClient(app)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
