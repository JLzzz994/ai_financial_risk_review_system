"""把角色数据范围转换为 SQLAlchemy 查询条件。"""

from uuid import UUID

from sqlalchemy import false, true
from sqlalchemy.sql.elements import ColumnElement

from app.errors import AuthorizationError
from app.schemas.auth import Principal, RoleCode


def filter_by_data_scope(
    principal: Principal,
    resource_type: str,
    *,
    owner_column: ColumnElement[bool] | None = None,
    assignee_column: ColumnElement[bool] | None = None,
    organization_column: ColumnElement[bool] | None = None,
    configuration_resource: bool = False,
) -> ColumnElement[bool]:
    """生成查询过滤条件；调用方必须传入资源表对应列，禁止从请求体推断用户。"""
    if principal.disabled or principal.status != "active":
        return false()
    if resource_type == "document":
        if RoleCode.APPLICANT in principal.roles and owner_column is not None:
            return owner_column == UUID(str(principal.user_id))
        if RoleCode.FINANCE in principal.roles and organization_column is not None:
            if principal.org_scope:
                return organization_column.in_(tuple(principal.org_scope))
            return false()
        return false()
    if resource_type == "approval_task":
        if RoleCode.APPROVER in principal.roles and assignee_column is not None:
            return assignee_column == UUID(str(principal.user_id))
        return false()
    if configuration_resource and RoleCode.ADMIN in principal.roles:
        return true()
    raise AuthorizationError("不支持该资源的数据范围过滤")
