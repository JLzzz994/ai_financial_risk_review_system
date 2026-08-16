"""权限和组织范围测试。"""

from uuid import uuid4

import pytest

from app.errors import AuthorizationError
from app.schemas.auth import PermissionCode, Principal, RoleCode
from app.services.permission_service import authorize, has_permission


def test_applicant_can_only_read_own_document() -> None:
    """申请人只能访问本人单据。"""
    user_id = uuid4()
    principal = Principal(user_id=user_id, username="applicant", roles=frozenset({RoleCode.APPLICANT}))
    assert has_permission(principal, PermissionCode.DOCUMENT_READ_OWN)
    authorize(principal, PermissionCode.DOCUMENT_READ_OWN, user_id)
    with pytest.raises(AuthorizationError):
        authorize(principal, PermissionCode.DOCUMENT_READ_OWN, uuid4())
