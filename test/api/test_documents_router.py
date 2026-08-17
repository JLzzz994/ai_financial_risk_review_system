"""费用报销单路由测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.documents import CreateDocumentCommand
from app.routers.documents import service


def test_create_document_route() -> None:
    """创建接口返回单据编号和草稿状态。"""
    response = TestClient(app).post("/api/v1/documents", json={"applicant_id": str(uuid4()), "applicant_department": "财务", "total_amount": "100.00", "apply_date": "2026-08-17", "reason_text": "差旅"})
    assert response.status_code == 201
    assert response.json()["document_status"] == "draft"


def test_submit_route_creates_version() -> None:
    """提交接口生成版本号。"""
    applicant = uuid4()
    draft = service.create_draft(CreateDocumentCommand(applicant_id=applicant, applicant_department="财务", total_amount="100.00", apply_date="2026-08-17", reason_text="差旅"))
    response = TestClient(app).post(f"/api/v1/documents/{draft.document_id}/submit?actor_id={applicant}&expected_state_version=1")
    assert response.status_code == 200
    assert response.json()["version_no"] == 1
