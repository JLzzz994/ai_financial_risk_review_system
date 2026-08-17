"""人工复核接口测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.routers.risk import manual_review_service
from engines.risk.contracts import RiskFinding


def test_manual_review_requires_comment_and_preserves_original_finding() -> None:
    """人工复核必须有意见，且只更新复核记录状态。"""
    version_id = uuid4()
    finding = RiskFinding(rule_code="amount.threshold", level="medium", status="manual_review", message="证据不足")
    record = manual_review_service.create(version_id, finding)
    response = TestClient(app).post(f"/api/v1/document-versions/{version_id}/risk/manual-reviews/{record.review_id}", json={"reviewer_id": str(uuid4()), "status": "confirmed", "comment": "已核对原始凭证"})
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert finding.status == "manual_review"
