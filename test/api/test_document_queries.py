"""单据查询和版本历史接口测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.routers.documents import service
from app.schemas.documents import CreateDocumentCommand


def test_document_query_and_version_history() -> None:
    """查询接口返回当前状态和历史版本。"""
    applicant = uuid4()
    draft = service.create_draft(CreateDocumentCommand(applicant_id=applicant, applicant_department="财务", total_amount="100.00", apply_date="2026-08-17", reason_text="差旅"))
    client = TestClient(app)
    assert client.get(f"/api/v1/documents/{draft.document_id}").status_code == 200
    assert client.get(f"/api/v1/documents/{draft.document_id}/versions").json() == []
