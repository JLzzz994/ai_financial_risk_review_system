"""PostgreSQL 用户仓储。"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extended import roles, user_roles, users
from app.schemas.auth import Principal, RoleCode


@dataclass(frozen=True, slots=True)
class StoredUser:
    """认证服务所需的最小用户记录，不暴露 ORM 行。"""

    user_id: UUID
    username: str
    password_hash: str
    principal: Principal


class SqlUserRepository:
    """从 PostgreSQL 查询用户、角色和组织授权范围。"""

    async def find_by_username(self, session: AsyncSession, username: str) -> StoredUser | None:
        """按登录名查询用户及其角色，禁用用户也返回供服务层统一拒绝。"""
        result = await session.execute(select(users).where(users.c.username == username))
        row = result.mappings().first()
        if row is None:
            return None
        return await self._to_stored_user(session, row)

    async def find_by_id(self, session: AsyncSession, user_id: UUID) -> StoredUser | None:
        """按用户 ID 查询最新权限版本，确保旧令牌可被识别为过期。"""
        result = await session.execute(select(users).where(users.c.id == user_id))
        row = result.mappings().first()
        if row is None:
            return None
        return await self._to_stored_user(session, row)

    async def _to_stored_user(self, session: AsyncSession, row: Any) -> StoredUser:
        """将用户行和关联授权转换为领域主体。"""
        user_id = UUID(str(row["id"]))
        role_result = await session.execute(
            select(roles.c.role_code, roles.c.status, user_roles.c.org_scope_json)
            .join(user_roles, user_roles.c.role_id == roles.c.id)
            .where(user_roles.c.user_id == user_id)
        )
        role_rows = role_result.mappings().all()
        role_codes: set[RoleCode] = set()
        org_scope = {str(row["organization_id"])}
        for role_row in role_rows:
            if role_row["status"] != "active":
                continue
            try:
                role_codes.add(RoleCode(str(role_row["role_code"])))
            except ValueError:
                # 数据库中的未知角色不应阻断登录，但也不能授予隐含权限。
                continue
            org_scope.update(self._scope_values(role_row["org_scope_json"]))
        status = str(row["status"])
        principal = Principal(
            user_id=user_id,
            username=str(row["username"]),
            roles=frozenset(role_codes),
            permission_version=int(row["permission_version"]),
            org_scope=frozenset(org_scope),
            disabled=status != "active",
            status=status,
        )
        return StoredUser(
            user_id=user_id,
            username=str(row["username"]),
            password_hash=str(row["password_hash"]),
            principal=principal,
        )

    @staticmethod
    def _scope_values(value: object) -> set[str]:
        """兼容组织范围 JSON 的对象、列表和单值格式。"""
        if isinstance(value, Mapping):
            candidates = value.get("organization_ids", value.get("org_ids", []))
        else:
            candidates = value
        if isinstance(candidates, str):
            return {candidates}
        if isinstance(candidates, (list, tuple, set, frozenset)):
            return {str(item) for item in candidates if item is not None}
        return set()


__all__ = ["SqlUserRepository", "StoredUser"]
