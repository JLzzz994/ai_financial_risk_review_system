# 认证与权限模块——模块级 SPEC

> 状态：已生成，待用户审核
>
> 粒度：模块级；用于确认认证、角色权限和数据权限的边界、数据结构、业务流程、代码文件、接口范围和验收点。
>
> 【重点审核】本节点重点请审核：Token 撤销策略、角色与数据范围映射、管理员可配置范围、登录失败策略。

## 1. 模块目标与范围

本模块为单据、附件、风险复核、审批和报告模块提供统一身份认证、功能权限和数据权限。Settings 是唯一配置入口：JWT secret、issuer、algorithm、expiry、密码哈希参数、Redis 撤销和限流参数均由配置提供，业务代码不得写死。MVP 使用用户名/密码登录，签发短期 Bearer Token；Redis 保存 Token 撤销标记和登录失败限流状态。Redis 撤销或限流依赖不可用时，认证按 fail closed 处理。

包含：

- 登录、当前用户、退出登录（Token 撤销）；
- 用户启用/禁用、角色和权限关系读取；
- 功能权限校验（菜单、接口和操作）；
- 数据范围校验：申请人本人、审批人分配任务、财务授权组织范围、管理员配置权限；
- 统一鉴权上下文和审计字段。

不包含：外部统一身份认证、复杂组织树维护、细粒度字段脱敏策略和多因素认证；这些作为后续扩展点。权限只覆盖《财务风险评审项目说明.md》要求的登录、角色授权、数据权限、用户/角色/权限维护和审计，不额外扩展权限模型。

## 2. 数据结构

复用数据对象文档中的 `users`、`roles`、`permissions`、`user_roles`、`role_permissions` 和 `audit_logs`。用户主组织使用 `users.organization_id`；角色授权组织集合使用 `user_roles.org_scope_json`，不新增独立 `organizations` 表。机器可读状态全部使用小写：

| 对象 | 状态/关键字段 | 约束 |
|---|---|---|
| 用户 | `status=active/disabled`、`password_hash`、`organization_id`、`permission_version` | 禁用用户不能登录；角色或权限变更时递增 `permission_version`；密码只保存安全哈希 |
| 角色 | `status=active/disabled`、`role_code` | `role_code` 全局唯一，权限通过关联表授予 |
| 权限 | `permission_code`、`resource`、`action` | 代码格式建议 `resource:action`，如 `approval_task:decide` |
| 用户角色 | `user_id`、`role_id`、`org_scope_json` | 保存角色授权组织集合；越权范围由后端裁剪 |
| 审计日志 | `actor_id`、`action`、`resource_type`、`resource_id`、`request_id`、`client_ip`、`user_agent`、`metadata_json` | 登录、失败、退出、权限拒绝和权限配置变更均记录；不保存密码、完整 Token 或敏感原文 |
| Access Token | JWT `sub`、`jti`、`exp`、`permission_version` | 不新增持久化表；Redis 以 `auth:revoked:{jti}` 保存撤销标记，TTL 至 Token 过期 |

### 2.1 默认角色与数据范围

| 角色 | 典型权限 | 数据范围 |
|---|---|---|
| `applicant` | 创建/编辑/提交本人单据，查看本人风险和报告 | `applicant_id = current_user.id` |
| `approver` | 查看分配任务、查看证据、提交审批决定 | `approval_tasks.assignee_id = current_user.id` |
| `finance` | 查看风险、报告和审批结果 | `organization_id ∈ current_user.authorized_org_ids`，集合由 `org_scope_json` 解析 |
| `admin` | 用户、角色、流程模板、规则和系统配置 | 配置资源范围；不默认获得全部业务单据读取权 |

## 3. 业务流程

1. 用户提交用户名和密码；服务查询 `status=active` 用户并校验密码哈希。
2. 校验通过后生成包含 `sub`、`jti`、`iat`、`exp` 和权限版本的 Token，返回登录用户和过期时间，并写入审计日志。
3. 每次请求由 `get_current_user` 解析 Token，检查签名、过期时间、Redis 撤销标记、用户状态和权限版本。
4. 路由先执行功能权限依赖，再执行数据范围过滤；Service 层再次校验资源归属，避免仅依赖前端隐藏按钮。权限和组织范围始终由后端校验。
5. 退出登录将当前 `jti` 写入 Redis 撤销集合，TTL 设置为 Token 剩余有效期，并记录审计日志。
6. 用户被禁用后，新请求立即拒绝；已签发 Token 通过用户状态检查失效，无需等待 Token 自然过期。认证成功、认证拒绝、权限拒绝和权限/组织范围变更均写入脱敏审计。

### 3.1 与审批流程配置的关系

管理员可以配置和发布审批模板，但认证模块只负责确认其拥有 `workflow:manage` 权限及配置范围。审批实例仍由固定顺序状态机执行，Agent 无权借助 Token 或工具调用改变节点。

## 4. 核心代码文件

```text
app/
├── routers/auth.py
├── schemas/auth.py
├── services/auth_service.py
├── dependencies/auth.py
└── exceptions/auth.py
engines/
├── auth/password_hasher.py
├── auth/token_service.py
├── auth/permission_checker.py
└── common/repositories/auth_repository.py
front/src/
├── views/auth/LoginView.vue
├── api/auth.ts
├── stores/auth.ts
└── router/guards.ts
test/
├── app/auth/test_auth_router.py
├── engines/auth/test_token_service.py
└── engines/auth/test_permission_checker.py
```

## 5. 接口范围

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | 公开 | 登录并签发 Token |
| `GET` | `/api/v1/auth/me` | Bearer Token | 获取当前用户、角色、权限和组织范围 |
| `POST` | `/api/v1/auth/logout` | Bearer Token | 撤销当前 Token；作为补充接口纳入统一认证模块 |
| `GET` | `/api/v1/admin/users` | `user:read` | 查询用户列表 |
| `POST` | `/api/v1/admin/users` | `user:create` | 创建用户 |
| `PATCH` | `/api/v1/admin/users/{user_id}` | `user:update` | 修改用户状态、基本信息或组织 |
| `GET` | `/api/v1/admin/roles` | `role:read` | 查询角色及其权限 |
| `POST` | `/api/v1/admin/roles` | `role:create` | 创建角色 |
| `PATCH` | `/api/v1/admin/roles/{role_id}` | `role:update` | 修改角色名称和状态 |
| `GET` | `/api/v1/admin/permissions` | `permission:read` | 查询可分配权限 |
| `PUT` | `/api/v1/admin/roles/{role_id}/permissions` | `role_permission:manage` | 替换角色权限集合 |
| `PUT` | `/api/v1/admin/users/{user_id}/roles` | `user_role:manage` | 替换用户角色及组织范围 |

统一错误：`INVALID_CREDENTIALS`、`ACCOUNT_DISABLED`、`TOKEN_EXPIRED`、`TOKEN_REVOKED`、`FORBIDDEN`。登录失败响应不区分“用户不存在”和“密码错误”。

## 6. 验收标准

- [ ] 有效用户可以登录并访问 `/api/v1/auth/me`。
- [ ] 禁用用户、过期 Token、被撤销 Token 均不能访问受保护接口。
- [ ] 申请人、审批人、财务和管理员的默认数据范围符合 R-03。
- [ ] 功能权限不足返回 403，并写入审计日志。
- [ ] Token 撤销和登录失败限流使用 Redis TTL；Redis 依赖不可用时认证关闭，不产生绕过认证的降级路径。
- [ ] 密码、Token、登录失败日志不记录明文敏感信息。
- [ ] 管理员不能禁用自己、移除自己的最后一个 `admin` 角色或使系统失去最后一个可用管理员。
- [ ] 角色、权限和组织范围变更写入审计，并使目标用户旧 Token 失效。
- [ ] 权限目录由系统内置和迁移管理，管理员只能查看和分配，不能任意创建或删除权限。

## 7. 【重点审核】

1. Token 是否采用短期 JWT + Redis 撤销，而不是新增 Token 持久化表。
2. `admin` 是否仅管理配置，不默认读取所有业务单据。
3. `finance` 的组织范围是否来自角色授权并支持多组织。
4. 是否需要在 MVP 增加刷新 Token、多因素认证或外部 SSO。
