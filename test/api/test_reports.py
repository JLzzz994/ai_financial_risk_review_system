"""报告接口测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.routers.reports import service


def test_report_list_and_detail_are_version_bound() -> None:
    """列表返回摘要，详情返回完整内容。"""
    version_id = uuid4()
    report = service.finalize_report(version_id, "风险报告")
    client = TestClient(app)
    assert client.get(f"/api/v1/document-versions/{version_id}/reports").json()[0]["report_id"] == str(report.report_id)
    assert client.get(f"/api/v1/reports/{report.report_id}").json()["content"] == "风险报告"
