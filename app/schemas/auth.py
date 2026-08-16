"""认证和权限边界模型。"""

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
    APPROVAL_DECIDE = "approval:decide"
    FINANCE_READ_SCOPED = "finance:read:scoped"
    CONFIG_MANAGE = "config:manage"


class LoginCommand(BaseModel):
    """登录请求，不保存明文密码。"""

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class AuthToken(BaseModel):
    """认证成功后的令牌响应。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 1800


class Principal(BaseModel):
    """当前请求主体及其组织数据范围。"""

    user_id: UUID
    username: str
    roles: frozenset[RoleCode] = frozenset()
    permission_version: int = 1
    org_scope: frozenset[str] = frozenset()
    disabled: bool = False
