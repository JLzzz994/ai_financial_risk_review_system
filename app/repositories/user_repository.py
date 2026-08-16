"""用户仓储契约，具体 SQLAlchemy 实现后续接入。"""

from typing import Protocol
from uuid import UUID

from app.schemas.auth import Principal


class UserRepository(Protocol):
    """认证服务依赖的用户查询接口。"""

    async def find_active_by_id(self, user_id: UUID) -> Principal | None:
        """按用户 ID 查询启用主体。"""


class InMemoryUserRepository:
    """仅供单元测试使用的内存仓储。"""

    def __init__(self, principals: tuple[Principal, ...] = ()) -> None:
        """初始化测试主体。"""
        self._principals = {principal.user_id: principal for principal in principals}

    async def find_active_by_id(self, user_id: UUID) -> Principal | None:
        """返回未禁用主体，禁用用户视为不存在。"""
        principal = self._principals.get(user_id)
        return principal if principal and not principal.disabled else None
