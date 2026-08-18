"""认证和权限边界模型。"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class RoleCode(StrEnum):
    """系统内置角色编码。"""

    APPLICANT = "applicant"
    APPROVER = "approver"
    FINANCE = "finance"
    ADMIN = "admin"


class PermissionCode(StrEnum):
    """最小权限目录。"""

    DOCUMENT_READ_OWN = "document:read:own"
    DOCUMENT_CREATE = "document:create"
    DOCUMENT_UPDATE_OWN = "document:update:own"
    DOCUMENT_SUBMIT_OWN = "document:submit:own"
    APPROVAL_DECIDE = "approval:decide"
    APPROVAL_READ_ASSIGNED = "approval:read:assigned"
    FINANCE_READ_SCOPED = "finance:read:scoped"
    CONFIG_MANAGE = "config:manage"
    CONFIG_READ = "config:read"
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    ROLE_READ = "role:read"
    ROLE_CREATE = "role:create"
    ROLE_UPDATE = "role:update"
    PERMISSION_READ = "permission:read"
    ROLE_PERMISSION_MANAGE = "role_permission:manage"
    USER_ROLE_MANAGE = "user_role:manage"


class LoginCommand(BaseModel):
    """登录请求，不保存明文密码。"""

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class AuthToken(BaseModel):
    """认证成功后的令牌响应。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 1800
    expires_at: datetime | None = None
    user: "Principal | None" = None


class AuthContext(BaseModel):
    """完成认证后的可传递上下文，不包含密码或完整令牌。"""

    user_id: UUID
    roles: frozenset[RoleCode] = frozenset()
    permissions: frozenset[PermissionCode] = frozenset()
    organization_ids: frozenset[str] = frozenset()
    token_jti: str


class Principal(BaseModel):
    """当前请求主体及其组织数据范围。"""

    user_id: UUID
    username: str
    roles: frozenset[RoleCode] = frozenset()
    permission_version: int = 1
    org_scope: frozenset[str] = frozenset()
    disabled: bool = False
    status: str = "active"

    @property
    def organization_ids(self) -> frozenset[str]:
        """返回组织范围的兼容命名，避免业务层重复维护两套字段。"""
        return self.org_scope
