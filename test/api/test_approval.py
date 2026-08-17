"""审批 API 测试。"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.routers.approval import service


def test_only_assigned_approver_can_decide() -> None:
    """未分配任务拒绝提交审批决定。"""
    task_id = uuid4()
    response = TestClient(app).post(
        f"/api/v1/approval-tasks/{task_id}/decision",
        json={
            "approver_id": str(uuid4()),
            "decision": "approve",
            "comment": "同意",
            "idempotency_key": "k1",
        },
    )
    assert response.status_code == 403


def test_idempotency_header_is_used_for_approval_decision() -> None:
    """审批写接口优先使用标准 Idempotency-Key 请求头。"""
    task_id = uuid4()
    approver_id = uuid4()
    service.assign(task_id, approver_id)

    response = TestClient(app).post(
        f"/api/v1/approval-tasks/{task_id}/decision",
        headers={"Idempotency-Key": "header-key"},
        json={
            "approver_id": str(approver_id),
            "decision": "approve",
            "comment": "同意",
            "idempotency_key": "body-key",
        },
    )

    assert response.status_code == 200
    assert (task_id, "header-key") in service.idempotency
    assert (task_id, "body-key") not in service.idempotency
