# 认证与权限模块——方法级 SPEC

> 状态：已生成，待用户审核
>
> 依据：`03-模块级SPEC-认证与权限.md`、`财务风险评审项目说明.md`、`05-数据对象文档.md`。
>
> 【重点审核】本节点重点请审核：密码哈希算法、Token 有效期、Redis 撤销键、权限判断顺序和登录失败限流策略。

## 1. 方法清单

| 方法 | 文件 | 职责 |
|---|---|---|
| `login` | `app/services/auth_service.py` | 校验用户并签发 Token |
| `get_current_user` | `app/dependencies/auth.py` | 解析 Token、检查状态和撤销标记 |
| `logout` | `app/services/auth_service.py` | 写入 Token 撤销键 |
| `require_permission` | `app/dependencies/auth.py` | 校验功能权限 |
| `filter_by_data_scope` | `engines/auth/permission_checker.py` | 生成数据范围过滤条件 |
| `record_auth_audit` | `app/services/auth_service.py` | 记录认证与拒绝审计 |
| `list_users` | `app/services/user_admin_service.py` | 管理员查询用户 |
| `create_user` | `app/services/user_admin_service.py` | 管理员创建用户 |
| `update_user` | `app/services/user_admin_service.py` | 修改用户状态、基本信息和组织 |
| `list_roles` | `app/services/user_admin_service.py` | 查询角色及权限 |
| `create_role` | `app/services/user_admin_service.py` | 创建角色 |
| `update_role` | `app/services/user_admin_service.py` | 修改角色名称和状态 |
| `list_permissions` | `app/services/user_admin_service.py` | 查询可分配权限 |
| `replace_role_permissions` | `app/services/user_admin_service.py` | 原子替换角色权限 |
| `replace_user_roles` | `app/services/user_admin_service.py` | 原子替换角色和组织范围 |

## 2. `login`

### 输入

```json
{"username":"alice","password":"********"}
```

### 流程

1. 按用户名查询用户。
2. 用户不存在、状态不是 `active` 或密码校验失败时统一返回 `INVALID_CREDENTIALS`；Redis 同时按账号和 IP 记录失败次数，任一维度达到阈值后短时限流。Redis 限流依赖不可用时返回 `AUTH_DEPENDENCY_UNAVAILABLE`，不得继续认证。
3. 使用配置指定的密码哈希 Provider 校验密码；默认 Provider 为 Argon2id，Provider 选择和参数由 Settings 提供，业务代码不内置运行时切换。
4. 生成随机 `jti`，Token 有效期、secret、issuer 和 algorithm 均从 Settings 读取；将 `sub`、`jti`、`exp`、`permission_version` 写入 JWT。
5. 返回 `access_token`、`token_type=bearer`、`expires_at` 和用户摘要。
6. 记录成功或失败审计，但不记录密码和完整 Token。

### 响应

```json
{
  "access_token":"eyJ...",
  "token_type":"bearer",
  "expires_at":"2026-08-16T12:30:00+08:00",
  "user":{"id":"uuid","username":"alice","status":"active","roles":["applicant"]}
}
```

## 3. `get_current_user`

按顺序执行：读取 `Authorization: Bearer <token>` → 验签 → 校验 `exp` → 检查 `auth:revoked:{jti}` → 查询用户状态 → 加载角色和权限 → 构造 `AuthContext`。任何失败均返回 401，权限不足由后续依赖返回 403。

```python
class AuthContext(TypedDict):
    user_id: UUID
    roles: list[str]
    permissions: set[str]
    organization_ids: set[UUID]
    token_jti: str
```

## 4. `logout`

读取当前 Token 的 `jti` 和剩余 TTL，写入：

```text
auth:revoked:{jti} = 1, EX <remaining_seconds>
```

重复退出是幂等操作，返回 204；Redis 不可用时不应静默放行，接口返回 `AUTH_DEPENDENCY_UNAVAILABLE` 并记录告警；认证和限流均 fail closed。

## 5. `require_permission`

路由声明所需权限，例如 `require_permission("approval_task:decide")`。依赖先检查用户是否拥有权限，再进入 Service 的资源归属校验。权限码统一小写、冒号分隔；禁止从请求体中的 `user_id` 推断当前用户。

## 6. `filter_by_data_scope`

| 角色 | 过滤条件 |
|---|---|
| `applicant` | `financial_documents.applicant_id = current_user.id` |
| `approver` | `approval_tasks.assignee_id = current_user.id` |
| `finance` | `financial_documents.organization_id IN authorized_org_ids`；集合来自 `user_roles.org_scope_json` |
| `admin` | 仅对配置资源放宽；业务资源仍走显式授权 |

多角色取并集，但每条查询仍需附加资源类型对应的条件。更新和删除必须在同一事务中重新检查范围，避免 TOCTOU（检查与使用之间的竞态）。

## 7. 测试用例

- 正确密码登录成功，错误密码返回统一错误。
- `disabled` 用户不能登录；登录后被禁用的用户下一次请求立即失败。
- 过期、格式错误和 Redis 撤销 Token 分别返回 401。
- 缺少功能权限返回 403 并记录审计。
- 申请人不能读取他人单据，审批人不能读取未分配任务，财务不能读取授权组织外单据。
- 多角色并集和组织范围交集行为符合预期。
- 退出接口重复调用不重复产生异常；Redis 故障不会绕过认证。
- 登录失败限流覆盖账号和 IP 两个维度、审计脱敏和 Token 不落日志。
- 无管理员权限不能调用用户、角色和权限维护接口；管理员修改角色后相关用户旧 Token 失效。
- `update_user` 和 `replace_user_roles` 拒绝管理员自禁用、自移除最后一个管理员角色，以及禁用系统最后一个可用管理员。
- 管理员配置变更与 `permission_version` 更新在同一事务内提交，并记录变更前后摘要。
- `replace_role_permissions` 更新角色权限后，递增该角色所有关联用户的 `permission_version`。
- `list_permissions` 只返回系统内置权限目录；权限新增、删除和权限码变更必须通过代码版本与数据库迁移完成。
- `record_auth_audit` 记录 `actor_id`、动作、资源、请求 ID、客户端 IP、User-Agent 和脱敏摘要；审计记录只追加，业务用户不可修改或删除。

## 8. 待用户确认项

1. Token 有效期是否采用 30 分钟，MVP 是否暂不提供刷新 Token。
2. 是否接受 Argon2id 优先、bcrypt 兼容的密码哈希方案。
3. 登录失败限流是否采用 5 次失败 / 10 分钟锁定 15 分钟的默认值。
4. Redis 撤销和限流依赖不可用时统一按“认证失败关闭（fail closed）”处理。
