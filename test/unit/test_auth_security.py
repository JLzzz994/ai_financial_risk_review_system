"""认证与数据权限的安全边界测试。"""

import asyncio
from uuid import uuid4

import jwt
import pytest

from app.errors import AppError, AuthorizationError
from app.schemas.auth import PermissionCode, Principal, RoleCode
from app.services.auth_service import (
    InMemoryAuthService,
    InMemoryRevocationStore,
    RedisRevocationStore,
)
from app.services.permission_service import (
    authorize,
    can_access_resource,
    has_permission,
)


def test_login_token_contains_jti_and_expires_at() -> None:
    """登录令牌必须有唯一 jti 和明确过期时间，不能复用固定令牌。"""
    service = InMemoryAuthService()
    service.register("security-user", "secret")

    first = service.authenticate("security-user", "secret")
    second = service.authenticate("security-user", "secret")

    assert first.expires_at is not None
    assert first.user is not None
    first_claims = jwt.decode(first.access_token, options={"verify_signature": False})
    second_claims = jwt.decode(second.access_token, options={"verify_signature": False})
    assert first_claims["jti"] != second_claims["jti"]
    assert first_claims["permission_version"] == 1


def test_revoked_token_is_rejected_and_logout_is_idempotent() -> None:
    """退出后令牌进入撤销存储，重复退出仍保持幂等。"""
    revocations = InMemoryRevocationStore()
    service = InMemoryAuthService(revocation_store=revocations)
    service.register("logout-user", "secret")
    token = service.authenticate("logout-user", "secret")

    asyncio.run(service.logout(token.access_token))
    asyncio.run(service.logout(token.access_token))

    with pytest.raises(AppError) as error:
        asyncio.run(service.get_current_principal(token.access_token))
    assert error.value.code == "token_revoked"


def test_disabled_user_and_changed_permission_version_invalidate_old_token() -> None:
    """禁用用户或修改角色后，旧令牌不能继续建立认证上下文。"""
    service = InMemoryAuthService()
    principal = service.register("versioned-user", "secret", RoleCode.APPLICANT)
    token = service.authenticate("versioned-user", "secret")

    service.update_roles(principal.user_id, {RoleCode.FINANCE}, organization_ids={"org-1"})
    with pytest.raises(AppError) as version_error:
        asyncio.run(service.get_current_principal(token.access_token))
    assert version_error.value.code == "token_stale"

    fresh = service.authenticate("versioned-user", "secret")
    service.disable(principal.user_id)
    with pytest.raises(AppError) as disabled_error:
        asyncio.run(service.get_current_principal(fresh.access_token))
    assert disabled_error.value.code == "account_disabled"


def test_data_scope_covers_applicant_approver_finance_and_admin() -> None:
    """四类角色只能访问其规定的数据范围，管理员不默认读取业务单据。"""
    applicant_id = uuid4()
    approver_id = uuid4()
    applicant = Principal(
        user_id=applicant_id,
        username="applicant",
        roles=frozenset({RoleCode.APPLICANT}),
    )
    approver = Principal(
        user_id=approver_id,
        username="approver",
        roles=frozenset({RoleCode.APPROVER}),
    )
    finance = Principal(
        user_id=uuid4(),
        username="finance",
        roles=frozenset({RoleCode.FINANCE}),
        org_scope=frozenset({"org-a", "org-b"}),
    )
    admin = Principal(user_id=uuid4(), username="admin", roles=frozenset({RoleCode.ADMIN}))

    assert can_access_resource(applicant, "document", owner_id=applicant_id)
    assert not can_access_resource(applicant, "document", owner_id=uuid4())
    assert can_access_resource(approver, "approval_task", assignee_id=approver_id)
    assert not can_access_resource(approver, "approval_task", assignee_id=uuid4())
    assert can_access_resource(finance, "document", organization_id="org-a")
    assert not can_access_resource(finance, "document", organization_id="org-c")
    assert not can_access_resource(admin, "document", owner_id=applicant_id)
    assert can_access_resource(admin, "workflow", is_configuration_resource=True)


def test_permission_dependency_distinguishes_missing_permission_from_scope() -> None:
    """缺少功能权限和资源不在数据范围都返回统一 403。"""
    applicant_id = uuid4()
    principal = Principal(
        user_id=applicant_id,
        username="applicant",
        roles=frozenset({RoleCode.APPLICANT}),
    )

    with pytest.raises(AuthorizationError):
        authorize(principal, PermissionCode.APPROVAL_DECIDE)
    with pytest.raises(AuthorizationError):
        authorize(principal, PermissionCode.DOCUMENT_READ_OWN, uuid4())
    authorize(principal, PermissionCode.DOCUMENT_READ_OWN, applicant_id)
    assert has_permission(principal, PermissionCode.DOCUMENT_READ_OWN)


def test_redis_revocation_store_uses_namespaced_ttl_key() -> None:
    """Redis 撤销适配器按配置前缀写入 jti，并设置剩余 TTL。"""

    class FakeRedis:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}
            self.ttls: dict[str, int] = {}

        def set(self, key: str, value: str, *, ex: int) -> None:
            self.values[key] = value
            self.ttls[key] = ex

        def exists(self, key: str) -> int:
            return int(key in self.values)

    fake = FakeRedis()
    store = RedisRevocationStore(fake, key_prefix="test:revoked")

    store.revoke("jti-1", 120)

    assert fake.values == {"test:revoked:jti-1": "1"}
    assert fake.ttls["test:revoked:jti-1"] == 120
    assert store.is_revoked("jti-1")


def test_revocation_dependency_failure_fails_closed() -> None:
    """撤销存储不可用时，认证不能降级为仅验签。"""

    class BrokenStore(InMemoryRevocationStore):
        def is_revoked(self, jti: str) -> bool:
            del jti
            raise RuntimeError("redis down")

    service = InMemoryAuthService(revocation_store=BrokenStore())
    service.register("dependency-user", "secret")
    token = service.authenticate("dependency-user", "secret")

    with pytest.raises(AppError) as error:
        asyncio.run(service.get_current_principal(token.access_token))
    assert error.value.code == "auth_dependency_unavailable"
    assert error.value.status_code == 503
