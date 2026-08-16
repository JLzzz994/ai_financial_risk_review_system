"""认证主体的最小权限和组织范围校验。"""

from uuid import UUID

from app.errors import AuthorizationError
from app.schemas.auth import PermissionCode, Principal, RoleCode


ROLE_PERMISSIONS: dict[RoleCode, frozenset[PermissionCode]] = {
    RoleCode.APPLICANT: frozenset({PermissionCode.DOCUMENT_READ_OWN}),
    RoleCode.APPROVER: frozenset({PermissionCode.APPROVAL_DECIDE}),
    RoleCode.FINANCE: frozenset({PermissionCode.FINANCE_READ_SCOPED}),
    RoleCode.ADMIN: frozenset({PermissionCode.CONFIG_MANAGE}),
}


def has_permission(principal: Principal, permission: PermissionCode) -> bool:
    """判断主体是否拥有指定权限。"""
    return any(permission in ROLE_PERMISSIONS.get(role, frozenset()) for role in principal.roles)


def authorize(principal: Principal, permission: PermissionCode, resource_owner_id: UUID | None = None) -> None:
    """执行权限和本人数据范围校验，失败抛出统一授权异常。"""
    if principal.disabled or not has_permission(principal, permission):
        raise AuthorizationError("无权执行该操作")
    if permission == PermissionCode.DOCUMENT_READ_OWN and resource_owner_id != principal.user_id:
        raise AuthorizationError("只能访问本人单据")
