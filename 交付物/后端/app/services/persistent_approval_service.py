"""固定顺序审批的 PostgreSQL 服务。"""

from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.sql_approval_repository import SqlApprovalRepository
from app.schemas.approval import (
    ApprovalDecisionRecord,
    ApprovalDecisionResponse,
    ApprovalHistoryNode,
    ApprovalTaskPage,
    ApprovalTaskResponse,
    DecisionCode,
)
from app.schemas.auth import Principal
from engines.approval.state_machine import ApprovalDecision, next_document_status


class ApprovalIdempotencyStore(Protocol):
    """审批幂等结果缓存契约。"""

    def get(self, key: str) -> str | None:
        """按键读取序列化响应。"""

    def set(self, key: str, value: str, ex: int) -> object:
        """写入带过期时间的响应。"""


class RedisApprovalIdempotencyStore:
    """使用 Redis 保存短期审批幂等结果。"""

    def __init__(self, client: object | None = None) -> None:
        """延迟创建 Redis 客户端，方便单元测试注入 Fake。"""
        self._client = client

    @property
    def client(self) -> object:
        """获取 Redis 客户端。"""
        if self._client is None:
            from redis import Redis

            self._client = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    def get(self, key: str) -> str | None:
        """读取幂等结果。"""
        return self.client.get(key)  # type: ignore[attr-defined,no-any-return]

    def set(self, key: str, value: str, ex: int) -> object:
        """写入幂等结果并保留一天。"""
        return self.client.set(key, value, ex=ex)  # type: ignore[attr-defined]


class PersistentApprovalService:
    """在数据库事务中执行审批决定，AI 不参与状态变更。"""

    def __init__(
        self,
        repository: SqlApprovalRepository | None = None,
        idempotency_store: ApprovalIdempotencyStore | None = None,
    ) -> None:
        """注入仓储和幂等存储。"""
        self.repository = repository or SqlApprovalRepository()
        self.idempotency_store = idempotency_store or RedisApprovalIdempotencyStore()

    async def decide(
        self,
        session: AsyncSession,
        task_id: UUID,
        actor: Principal,
        decision: ApprovalDecision | str,
        comment: str,
        idempotency_key: str,
    ) -> ApprovalDecisionResponse:
        """锁定当前节点并提交审批人员决定。"""
        if not idempotency_key.strip():
            raise ValueError("幂等键不能为空")
        if not comment.strip():
            raise ValueError("审批决定必须填写意见")
        cache_key = f"financial-review:approval:{task_id}:{idempotency_key}"
        cached = self.idempotency_store.get(cache_key)
        if cached:
            return ApprovalDecisionResponse.model_validate_json(cached)
        try:
            approval_decision = ApprovalDecision(decision)
        except ValueError as exc:
            raise ValueError("审批决定必须为 approve、return 或 reject") from exc

        async with session.begin():
            context = await self.repository.lock_for_decision(session, task_id)
            if context is None:
                raise ValueError("审批任务不存在")
            if context.task.approver_id != actor.user_id:
                raise PermissionError("只有当前节点分配的审批人可以提交决定")
            if context.task.task_status != "pending":
                raise ValueError("审批任务状态不允许提交决定")
            if context.instance.get("current_node_id") != context.task.node_id:
                raise ValueError("当前不是该审批节点")
            is_last_node = context.next_node is None
            document_status = next_document_status(approval_decision, is_last_node)
            await self.repository.apply_decision(
                session,
                context,
                decision=approval_decision.value,
                document_status=document_status,
                comment=comment,
                actor_id=actor.user_id,
            )

        record = ApprovalDecisionRecord(
            record_id=context.task.id,
            task_id=task_id,
            approver_id=actor.user_id,
            decision=DecisionCode(approval_decision.value),
            comment=comment,
            created_at=context.task.created_at,
        )
        response = ApprovalDecisionResponse(
            task_id=task_id,
            document_status=document_status,
            record=record,
        )
        self.idempotency_store.set(cache_key, response.model_dump_json(), ex=86400)
        return response

    async def get_task(
        self, session: AsyncSession, task_id: UUID, actor: Principal
    ) -> ApprovalTaskResponse:
        """读取当前审批人的任务详情。"""
        task = await self.repository.get_view(session, task_id)
        if task is None:
            raise ValueError("审批任务不存在")
        if task.assignee_id != actor.user_id:
            raise PermissionError("只能查看分配给本人的审批任务")
        return task

    async def list_tasks(
        self,
        session: AsyncSession,
        actor: Principal,
        *,
        page: int = 1,
        page_size: int = 20,
        task_status: str | None = None,
    ) -> ApprovalTaskPage:
        """分页读取分配给当前审批人的任务。"""
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("分页参数不合法")
        return await self.repository.list_for_approver(
            session,
            actor.user_id,
            page=page,
            page_size=page_size,
            task_status=task_status,
        )

    async def history(
        self, session: AsyncSession, document_id: UUID, actor: Principal
    ) -> list[ApprovalHistoryNode]:
        """读取单据审批历史，权限由路由和任务范围共同控制。"""
        del actor
        return await self.repository.list_history(session, document_id)


__all__ = [
    "ApprovalIdempotencyStore",
    "PersistentApprovalService",
    "RedisApprovalIdempotencyStore",
]
