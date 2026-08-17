"""分析任务 API 和 SSE 事件接口测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_create_analysis_task_returns_queued_task_and_sse_event() -> None:
    """提交分析只排队，不在 API 进程同步执行长任务。"""
    client = TestClient(app)
    document_id, version_id = uuid4(), uuid4()
    response = client.post(
        f"/api/v1/documents/{document_id}/analysis",
        headers={"Idempotency-Key": "analysis-api-key"},
        json={"document_version_id": str(version_id)},
    )

    assert response.status_code == 202
    task = response.json()
    assert task["stage"] == "queued"
    events = client.get(f"/api/v1/analysis-tasks/{task['task_id']}/events")
    assert events.status_code == 200
    assert events.headers["content-type"].startswith("text/event-stream")
    assert '"type":"progress"' in events.text


def test_analysis_start_is_idempotent_for_same_header() -> None:
    """重复请求头不会产生第二个分析任务。"""
    client = TestClient(app)
    document_id, version_id = uuid4(), uuid4()
    path = f"/api/v1/documents/{document_id}/analysis"
    headers = {"Idempotency-Key": "same-api-key"}
    first = client.post(path, headers=headers, json={"document_version_id": str(version_id)})
    repeated = client.post(path, headers=headers, json={"document_version_id": str(version_id)})

    assert first.status_code == repeated.status_code == 202
    assert first.json()["task_id"] == repeated.json()["task_id"]
