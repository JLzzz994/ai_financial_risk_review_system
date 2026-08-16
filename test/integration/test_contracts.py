"""接口契约集成测试。"""

from fastapi.testclient import TestClient

from app.main import app


def test_openapi_contains_decision_and_report_endpoints() -> None:
    """OpenAPI 必须暴露统一审批和报告双接口。"""
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/api/v1/approval-tasks/{task_id}/decision" in paths
    assert "/api/v1/reports/{report_id}" in paths
    assert "/api/v1/document-versions/{document_version_id}/reports" in paths
