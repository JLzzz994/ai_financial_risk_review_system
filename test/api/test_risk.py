"""风险 API 测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_risk_without_evidence_enters_manual_review() -> None:
    """API 返回人工确认状态。"""
    response = TestClient(app).post(
        f"/api/v1/document-versions/{uuid4()}/risk/evaluate",
        json={"amount": "100", "supplier_name": "供应商"},
    )
    assert response.status_code == 200
    assert response.json()["findings"][0]["status"] == "manual_review"


def test_risk_with_evidence_returns_auditable_finding() -> None:
    """有证据时响应包含审计所需引用。"""
    attachment_id = str(uuid4())
    payload = {
        "amount": "10000.00",
        "supplier_name": "正常供应商",
        "evidence": {
            "attachment_id": attachment_id,
            "page_or_location": "page:1",
            "original_text": "报销金额 10000.00",
            "field_name": "amount",
            "confidence": "0.99",
            "rule_version": "amount-v1",
        },
    }
    response = TestClient(app).post(
        f"/api/v1/document-versions/{uuid4()}/risk/evaluate", json=payload
    )
    assert response.status_code == 200
    assert response.json()["findings"][0]["evidence"]["rule_version"] == "amount-v1"
