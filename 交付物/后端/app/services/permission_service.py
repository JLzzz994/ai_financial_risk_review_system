"""认证主体的功能权限和数据范围校验。"""

from uuid import UUID

from app.errors import AuthorizationError
from app.schemas.auth import PermissionCode, Principal, RoleCode

ROLE_PERMISSIONS: dict[RoleCode, frozenset[PermissionCode]] = {
    RoleCode.APPLICANT: frozenset(
        {
            PermissionCode.DOCUMENT_CREATE,
            PermissionCode.DOCUMENT_READ_OWN,
            PermissionCode.DOCUMENT_UPDATE_OWN,
            PermissionCode.DOCUMENT_SUBMIT_OWN,
        }
    ),
    RoleCode.APPROVER: frozenset(
        {PermissionCode.APPROVAL_DECIDE, PermissionCode.APPROVAL_READ_ASSIGNED}
    ),
    RoleCode.FINANCE: frozenset(
        {PermissionCode.FINANCE_READ_SCOPED, PermissionCode.CONFIG_READ}
    ),
    RoleCode.ADMIN: frozenset(
        {
            PermissionCode.CONFIG_MANAGE,
            PermissionCode.CONFIG_READ,
            PermissionCode.USER_READ,
            PermissionCode.USER_CREATE,
            PermissionCode.USER_UPDATE,
            PermissionCode.ROLE_READ,
            PermissionCode.ROLE_CREATE,
            PermissionCode.ROLE_UPDATE,
            PermissionCode.PERMISSION_READ,
            PermissionCode.ROLE_PERMISSION_MANAGE,
            PermissionCode.USER_ROLE_MANAGE,
        }
    ),
}


def has_permission(principal: Principal, permission: PermissionCode) -> bool:
    """判断主体是否拥有指定权限。"""
    return any(permission in ROLE_PERMISSIONS.get(role, frozenset()) for role in principal.roles)


def authorize(
    principal: Principal,
    permission: PermissionCode,
    resource_owner_id: UUID | None = None,
    *,
    resource_assignee_id: UUID | None = None,
    organization_id: str | None = None,
    is_configuration_resource: bool = False,
) -> None:
    """执行功能权限和资源数据范围校验，失败抛出统一授权异常。"""
    if (
        principal.disabled
        or principal.status != "active"
        or not has_permission(principal, permission)
    ):
        raise AuthorizationError("无权执行该操作")
    if permission in {
        PermissionCode.DOCUMENT_READ_OWN,
        PermissionCode.DOCUMENT_UPDATE_OWN,
        PermissionCode.DOCUMENT_SUBMIT_OWN,
    } and resource_owner_id != principal.user_id:
        raise AuthorizationError("只能访问本人单据")
    if permission in {PermissionCode.APPROVAL_DECIDE, PermissionCode.APPROVAL_READ_ASSIGNED}:
        if resource_assignee_id is not None and resource_assignee_id != principal.user_id:
            raise AuthorizationError("只能处理分配给本人的审批任务")
    if permission == PermissionCode.FINANCE_READ_SCOPED:
        if organization_id is not None and organization_id not in principal.org_scope:
            raise AuthorizationError("不在财务授权组织范围内")
    if RoleCode.ADMIN in principal.roles and not is_configuration_resource:
        business_permissions = {
            PermissionCode.DOCUMENT_READ_OWN,
            PermissionCode.DOCUMENT_CREATE,
            PermissionCode.DOCUMENT_UPDATE_OWN,
            PermissionCode.DOCUMENT_SUBMIT_OWN,
            PermissionCode.APPROVAL_DECIDE,
            PermissionCode.APPROVAL_READ_ASSIGNED,
            PermissionCode.FINANCE_READ_SCOPED,
        }
        if permission in business_permissions:
            raise AuthorizationError("管理员默认不具备业务单据数据读取权限")


def can_access_resource(
    principal: Principal,
    resource_type: str,
    *,
    owner_id: UUID | None = None,
    assignee_id: UUID | None = None,
    organization_id: str | None = None,
    is_configuration_resource: bool = False,
) -> bool:
    """按角色返回资源是否在主体数据范围内，供查询过滤和 Service 二次校验使用。"""
    if principal.disabled or principal.status != "active":
        return False
    if resource_type == "document":
        if RoleCode.APPLICANT in principal.roles and owner_id == principal.user_id:
            return True
        if RoleCode.FINANCE in principal.roles and organization_id in principal.org_scope:
            return True
        return False
    if resource_type == "approval_task":
        return RoleCode.APPROVER in principal.roles and assignee_id == principal.user_id
    if is_configuration_resource:
        return RoleCode.ADMIN in principal.roles and resource_type in {
            "workflow",
            "rule",
            "system_parameter",
            "user",
            "role",
            "permission",
        }
    return False
