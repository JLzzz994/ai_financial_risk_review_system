"""向 PostgreSQL 写入可重复执行的脱敏演示数据。

运行前请确保数据库已执行 ``alembic upgrade head``。数据库连接从
``DATABASE_URL`` 读取，适合本地开发库，不应指向生产数据库。
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from argon2 import PasswordHasher
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.core import ApprovalTask, DocumentVersion, FinancialDocument, ReviewReport
from app.models.extended import (
    analysis_tasks,
    approval_instances,
    approval_workflow_nodes,
    approval_workflows,
    audit_logs,
    document_line_items,
    document_status_logs,
    market_price_references,
    permissions,
    review_sessions,
    risk_findings,
    role_permissions,
    roles,
    session_messages,
    supplier_profiles,
    user_roles,
    users,
)

DEMO_PASSWORD = "Demo123!"
DEMO_ORGANIZATION_ID = UUID("11111111-1111-4111-8111-111111111111")
DEMO_DEPARTMENT_ID = UUID("22222222-2222-4222-8222-222222222222")
DEMO_DOCUMENT_ID = UUID("33333333-3333-4333-8333-333333333333")
DEMO_VERSION_ID = UUID("44444444-4444-4444-8444-444444444444")
DEMO_WORKFLOW_ID = UUID("55555555-5555-4555-8555-555555555555")
DEMO_FIRST_NODE_ID = UUID("66666666-6666-4666-8666-666666666666")
DEMO_SECOND_NODE_ID = UUID("77777777-7777-4777-8777-777777777777")
DEMO_INSTANCE_ID = UUID("88888888-8888-4888-8888-888888888888")
DEMO_TASK_ID = UUID("99999999-9999-4999-8999-999999999999")
DEMO_ANALYSIS_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
DEMO_FINDING_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
DEMO_REPORT_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
DEMO_SESSION_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
DEMO_MESSAGE_USER_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
DEMO_MESSAGE_ASSISTANT_ID = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
DEMO_STATUS_LOG_ID = UUID("11111111-aaaa-4aaa-8aaa-111111111111")
DEMO_AUDIT_ID = UUID("22222222-bbbb-4bbb-8bbb-222222222222")
DEMO_MARKET_PRICE_ID = UUID("33333333-cccc-4ccc-8ccc-333333333333")
DEMO_SUPPLIER_ID = UUID("44444444-dddd-4ddd-8ddd-444444444444")

DEMO_USER_IDS = {
    "demo_applicant": UUID("aaaaaaaa-0000-4000-8000-000000000001"),
    "demo_approver": UUID("aaaaaaaa-0000-4000-8000-000000000002"),
    "demo_finance": UUID("aaaaaaaa-0000-4000-8000-000000000003"),
}
DEMO_ROLE_IDS = {
    "applicant": UUID("bbbbbbbb-0000-4000-8000-000000000001"),
    "approver": UUID("bbbbbbbb-0000-4000-8000-000000000002"),
    "finance": UUID("bbbbbbbb-0000-4000-8000-000000000003"),
}


def build_demo_seed_plan() -> dict[str, object]:
    """返回稳定的演示种子摘要，便于测试和文档保持一致。"""
    return {
        "document_no": "DEMO-20260818-001",
        "usernames": tuple(DEMO_USER_IDS),
        "password": DEMO_PASSWORD,
        "organization_id": str(DEMO_ORGANIZATION_ID),
    }


async def _insert_ignore(
    connection: AsyncConnection,
    table: Any,
    values: dict[str, Any],
    conflict_columns: tuple[str, ...] = ("id",),
) -> None:
    """插入一行并在重复种子主键或唯一键时保持幂等。"""
    statement = pg_insert(table).values(**values).on_conflict_do_nothing(
        index_elements=list(conflict_columns)
    )
    await connection.execute(statement)


async def _seed(database_url: str) -> dict[str, str]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            password_hash = PasswordHasher().hash(DEMO_PASSWORD)
            await _seed_users(connection, password_hash)
            await _seed_document(connection)
            await _seed_approval(connection)
            await _seed_analysis(connection)
            await _seed_supporting_data(connection)
    finally:
        await engine.dispose()
    return {
        "document_id": str(DEMO_DOCUMENT_ID),
        "document_version_id": str(DEMO_VERSION_ID),
        "approval_task_id": str(DEMO_TASK_ID),
        "analysis_task_id": str(DEMO_ANALYSIS_ID),
        "report_id": str(DEMO_REPORT_ID),
        "session_id": str(DEMO_SESSION_ID),
    }


async def _seed_users(connection: AsyncConnection, password_hash: str) -> None:
    role_definitions = {
        "applicant": ("申请人", "document:create"),
        "approver": ("审批人员", "approval:decide"),
        "finance": ("财务人员", "finance:read:scoped"),
    }
    for role_code, (role_name, _) in role_definitions.items():
        await _insert_ignore(
            connection,
            roles,
            {"id": DEMO_ROLE_IDS[role_code], "role_code": role_code, "role_name": role_name},
            ("role_code",),
        )

    permission_definitions = {
        "document:create": ("创建单据", "document", "create"),
        "document:read:own": ("查看本人单据", "document", "read"),
        "document:submit:own": ("提交本人单据", "document", "submit"),
        "approval:decide": ("处理审批任务", "approval", "decide"),
        "approval:read:assigned": ("查看分配审批任务", "approval", "read"),
        "finance:read:scoped": ("查看授权范围单据", "finance", "read"),
    }
    permission_ids: dict[str, UUID] = {}
    for index, (code, (name, resource, action)) in enumerate(permission_definitions.items(), 1):
        permission_id = UUID(f"{index:08x}-0000-4000-8000-000000000001")
        permission_ids[code] = permission_id
        await _insert_ignore(
            connection,
            permissions,
            {
                "id": permission_id,
                "permission_code": code,
                "permission_name": name,
                "resource_type": resource,
                "action_type": action,
            },
            ("permission_code",),
        )

    user_definitions = {
        "demo_applicant": ("演示申请人", "申请人", "applicant"),
        "demo_approver": ("演示审批人", "审批人", "approver"),
        "demo_finance": ("演示财务", "财务人员", "finance"),
    }
    for username, (display_name, job_title, role_code) in user_definitions.items():
        await _insert_ignore(
            connection,
            users,
            {
                "id": DEMO_USER_IDS[username],
                "username": username,
                "display_name": display_name,
                "password_hash": password_hash,
                "organization_id": DEMO_ORGANIZATION_ID,
                "department_id": DEMO_DEPARTMENT_ID,
                "job_title": job_title,
            },
            ("username",),
        )
        await _insert_ignore(
            connection,
            user_roles,
            {
                "id": UUID(f"{DEMO_USER_IDS[username].int + 1:032x}"),
                "user_id": DEMO_USER_IDS[username],
                "role_id": DEMO_ROLE_IDS[role_code],
                "org_scope_json": {"organization_ids": [str(DEMO_ORGANIZATION_ID)]},
            },
            ("user_id", "role_id"),
        )
        for code in permission_definitions:
            if code.startswith("document:") and role_code == "applicant":
                permission_role = True
            elif code.startswith("approval:") and role_code == "approver":
                permission_role = True
            elif code.startswith("finance:") and role_code == "finance":
                permission_role = True
            else:
                permission_role = False
            if permission_role:
                await _insert_ignore(
                    connection,
                    role_permissions,
                    {
                        "id": UUID(
                            f"{DEMO_ROLE_IDS[role_code].int + permission_ids[code].int:032x}"
                        ),
                        "role_id": DEMO_ROLE_IDS[role_code],
                        "permission_id": permission_ids[code],
                    },
                    ("role_id", "permission_id"),
                )


async def _seed_document(connection: AsyncConnection) -> None:
    snapshot = {
        "document_type": "expense_reimbursement",
        "document_no": "DEMO-20260818-001",
        "total_amount": "138.00",
        "currency": "CNY",
        "expense_category": "差旅交通",
        "reason_text": "演示用市内交通报销",
    }
    await _insert_ignore(
        connection,
        FinancialDocument.__table__,
        {
            "id": DEMO_DOCUMENT_ID,
            "document_type": "expense_reimbursement",
            "document_no": "DEMO-20260818-001",
            "applicant_id": DEMO_USER_IDS["demo_applicant"],
            "applicant_department": "演示财务部",
            "budget_department": "演示财务部",
            "expense_category": "差旅交通",
            "total_amount": Decimal("138.00"),
            "currency": "CNY",
            "apply_date": date(2026, 8, 18),
            "reason_text": "演示用市内交通报销",
            "document_payload": {"demo": True, "items": [snapshot]},
            "document_status": "pending_approval",
            "current_version": 1,
            "document_state_version": 1,
        },
    )
    await _insert_ignore(
        connection,
        DocumentVersion.__table__,
        {
            "id": DEMO_VERSION_ID,
            "document_id": DEMO_DOCUMENT_ID,
            "version_no": 1,
            "document_snapshot_json": snapshot,
            "created_by": DEMO_USER_IDS["demo_applicant"],
        },
        ("document_id", "version_no"),
    )
    for item_id, line_no, name, amount in (
        (UUID("55555555-aaaa-4aaa-8aaa-555555555555"), 1, "出租车", Decimal("80.00")),
        (UUID("66666666-bbbb-4bbb-8bbb-666666666666"), 2, "网约车", Decimal("58.00")),
    ):
        await _insert_ignore(
            connection,
            document_line_items,
            {
                "id": item_id,
                "document_id": DEMO_DOCUMENT_ID,
                "document_version_id": DEMO_VERSION_ID,
                "item_type": "expense",
                "item_name": name,
                "expense_date": date(2026, 8, 17),
                "expense_location": "上海市",
                "quantity": Decimal("1"),
                "unit_price": amount,
                "amount": amount,
                "currency": "CNY",
                "line_no": line_no,
            },
            ("document_version_id", "line_no"),
        )
    await _insert_ignore(
        connection,
        document_status_logs,
        {
            "id": DEMO_STATUS_LOG_ID,
            "document_id": DEMO_DOCUMENT_ID,
            "document_version_id": DEMO_VERSION_ID,
            "from_status": "draft",
            "to_status": "pending_approval",
            "operator_id": DEMO_USER_IDS["demo_applicant"],
            "remark": "演示数据初始化",
        },
    )


async def _seed_approval(connection: AsyncConnection) -> None:
    await _insert_ignore(
        connection,
        approval_workflows,
        {
            "id": DEMO_WORKFLOW_ID,
            "workflow_name": "费用报销演示审批流",
            "document_type": "expense_reimbursement",
            "workflow_code": "demo-expense-sequential",
            "workflow_version": 1,
            "published": True,
            "match_conditions_json": {"demo": True},
            "approval_mode": "sequential",
            "status": "published",
            "version_no": 1,
        },
    )
    for node_id, name, order, role, user_id in (
        (DEMO_FIRST_NODE_ID, "部门审批", 1, "approver", DEMO_USER_IDS["demo_approver"]),
        (DEMO_SECOND_NODE_ID, "财务复核", 2, "finance", DEMO_USER_IDS["demo_finance"]),
    ):
        await _insert_ignore(
            connection,
            approval_workflow_nodes,
            {
                "id": node_id,
                "workflow_id": DEMO_WORKFLOW_ID,
                "node_name": name,
                "node_order": order,
                "approver_role": role,
                "approver_scope_json": {"organization_ids": [str(DEMO_ORGANIZATION_ID)]},
                "primary_approver_id": user_id,
                "approval_mode": "sequential",
            },
            ("workflow_id", "node_order"),
        )
    await _insert_ignore(
        connection,
        approval_instances,
        {
            "id": DEMO_INSTANCE_ID,
            "workflow_id": DEMO_WORKFLOW_ID,
            "workflow_version_no": 1,
            "document_id": DEMO_DOCUMENT_ID,
            "document_version_id": DEMO_VERSION_ID,
            "instance_status": "running",
            "current_node_id": DEMO_FIRST_NODE_ID,
        },
    )
    await _insert_ignore(
        connection,
        ApprovalTask.__table__,
        {
            "id": DEMO_TASK_ID,
            "instance_id": DEMO_INSTANCE_ID,
            "node_id": DEMO_FIRST_NODE_ID,
            "approver_id": DEMO_USER_IDS["demo_approver"],
            "task_status": "pending",
            "created_at": datetime(2026, 8, 18),
        },
    )


async def _seed_analysis(connection: AsyncConnection) -> None:
    await _insert_ignore(
        connection,
        analysis_tasks,
        {
            "id": DEMO_ANALYSIS_ID,
            "document_id": DEMO_DOCUMENT_ID,
            "document_version_id": DEMO_VERSION_ID,
            "task_status": "succeeded",
            "current_step": "completed",
            "rule_version": "demo-v1",
            "model_metadata_json": {"provider": "demo", "model": "none"},
            "retry_count": 0,
            "idempotency_key": "demo-expense-analysis-v1",
        },
        ("idempotency_key",),
    )
    await _insert_ignore(
        connection,
        risk_findings,
        {
            "id": DEMO_FINDING_ID,
            "task_id": DEMO_ANALYSIS_ID,
            "document_version_id": DEMO_VERSION_ID,
            "risk_type": "amount_consistency",
            "risk_level": "low",
            "risk_title": "演示金额一致",
            "description": "单据总金额与明细合计一致，未发现演示数据异常。",
            "actual_value_json": {"document_total": "138.00", "line_total": "138.00"},
            "reference_value_json": {"source": "demo-seed"},
            "threshold_json": {"tolerance": "0.00"},
            "evidence_json": {"document_version_id": str(DEMO_VERSION_ID)},
            "rule_version": "demo-v1",
            "model_metadata_json": {"provider": "demo"},
            "suggestion_text": "可继续人工审批。",
            "review_status": "pending",
        },
    )
    await _insert_ignore(
        connection,
        ReviewReport.__table__,
        {
            "id": DEMO_REPORT_ID,
            "task_id": DEMO_ANALYSIS_ID,
            "document_id": DEMO_DOCUMENT_ID,
            "document_version_id": DEMO_VERSION_ID,
            "report_status": "final",
            "overall_risk_level": "low",
            "risk_summary_json": {"low": 1, "medium": 0, "high": 0},
            "amount_comparison_json": {"document_total": "138.00", "line_total": "138.00"},
            "recommendation": "pass_suggested",
            "report_markdown": "演示报告：金额与明细一致，建议由审批人员继续处理。",
            "generated_by": "demo-seeder",
            "report_version": 1,
            "report_content": {"demo": True},
        },
    )


async def _seed_supporting_data(connection: AsyncConnection) -> None:
    await _insert_ignore(
        connection,
        review_sessions,
        {
            "id": DEMO_SESSION_ID,
            "user_id": DEMO_USER_IDS["demo_applicant"],
            "document_id": DEMO_DOCUMENT_ID,
            "document_version_id": DEMO_VERSION_ID,
            "document_type": "expense_reimbursement",
            "document_no": "DEMO-20260818-001",
            "session_status": "waiting_human",
            "slot_state_json": {"document_type": "expense_reimbursement", "confirmed": True},
            "state_version": 1,
        },
    )
    await _insert_ignore(
        connection,
        session_messages,
        {
            "id": DEMO_MESSAGE_USER_ID,
            "session_id": DEMO_SESSION_ID,
            "role": "user",
            "content": "请查看演示费用报销单。",
            "message_type": "text",
            "metadata_json": {"demo": True},
        },
    )
    await _insert_ignore(
        connection,
        session_messages,
        {
            "id": DEMO_MESSAGE_ASSISTANT_ID,
            "session_id": DEMO_SESSION_ID,
            "role": "assistant",
            "content": "已定位演示单据 DEMO-20260818-001。",
            "message_type": "task_update",
            "metadata_json": {"document_id": str(DEMO_DOCUMENT_ID)},
        },
    )
    await _insert_ignore(
        connection,
        market_price_references,
        {
            "id": DEMO_MARKET_PRICE_ID,
            "item_name": "市内交通",
            "specification": "演示参考",
            "region": "上海市",
            "price_min": Decimal("0.00"),
            "price_max": Decimal("200.00"),
            "currency": "CNY",
            "source_name": "demo-seed",
            "effective_date": date(2026, 1, 1),
            "status": "active",
        },
    )
    await _insert_ignore(
        connection,
        supplier_profiles,
        {
            "id": DEMO_SUPPLIER_ID,
            "supplier_code": "DEMO-SUP-001",
            "supplier_name": "演示供应商",
            "credit_status": "normal",
            "blacklist_status": "normal",
            "risk_tags_json": [],
            "bank_accounts_json": {"account": "****1234"},
            "historical_risk_json": {"source": "demo-seed"},
        },
        ("supplier_code",),
    )
    await _insert_ignore(
        connection,
        audit_logs,
        {
            "id": DEMO_AUDIT_ID,
            "user_id": DEMO_USER_IDS["demo_applicant"],
            "actor_id": DEMO_USER_IDS["demo_applicant"],
            "action_type": "demo_seed",
            "action": "seed_demo_data",
            "resource_type": "financial_document",
            "resource_id": DEMO_DOCUMENT_ID,
            "detail_json": {"source": "demo-seed", "redacted": True},
            "ip_address": "127.0.0.1",
        },
    )


def main() -> None:
    """执行演示数据种子并打印可复制的资源 ID。"""
    summary = asyncio.run(_seed(settings.database_url))
    print("演示数据已写入 PostgreSQL：")
    for name, value in summary.items():
        print(f"- {name}: {value}")
    print(f"- demo accounts password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
