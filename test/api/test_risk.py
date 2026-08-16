"""风险 API 测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_risk_without_evidence_enters_manual_review() -> None:
    """API 返回人工确认状态。"""
    response = TestClient(app).post(f"/api/v1/document-versions/{uuid4()}/risk/evaluate", json={"amount": "100", "supplier_name": "供应商"})
    assert response.status_code == 200
    assert response.json()["findings"][0]["status"] == "manual_review"
