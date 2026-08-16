"""健康检查接口的单元测试。"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    """验证存活检查返回固定的健康状态。"""
    client = TestClient(app)
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_endpoint() -> None:
    """验证就绪检查返回固定的就绪状态。"""
    client = TestClient(app)
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
