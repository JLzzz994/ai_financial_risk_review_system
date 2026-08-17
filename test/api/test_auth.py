"""认证 API 的安全失败行为测试。"""

from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import auth_service


def test_login_returns_jwt_for_registered_user() -> None:
    """注册用户可以获得短期 JWT。"""
    auth_service.register("demo", "secret")
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"username": "demo", "password": "secret"})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


def test_me_requires_bearer_token() -> None:
    """未携带令牌时返回 401。"""
    client = TestClient(app)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
