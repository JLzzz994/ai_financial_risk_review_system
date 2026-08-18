# 财务风险审核 · 前端（front/）

Vue 3 + TypeScript + Vite + Pinia + Vue Router 实现，覆盖 SPEC 19 定义的 14 个页面，视觉 token 复刻 `财务评审文档/03-页面原型/`。

## 命令

```powershell
Set-Location front
npm ci            # 或 npm install
npm run dev       # 开发服务器（默认 http://localhost:5173，mock 模式）
npm run lint
npm run type-check
npm run build     # 类型检查 + 生产构建
npm run test:unit # vitest 单元测试
```

## 环境变量

- `VITE_API_BASE_URL`：API 前缀，默认 `/api/v1`（dev 经 Vite 代理到 `127.0.0.1:8000`，生产建议 nginx 反代）。
- `VITE_ENABLE_MOCK`：`true` 时启用开发 mock 层（拦截 fetch，按 SPEC 接口返回示例数据并推进状态机）。后端 OpenAPI 固化联调时置为 `false`。
- `VITE_SHOW_API_HINTS`：仅调试时显示组件内的 API 路径提示，默认 `false`；业务页面默认不展示接口地址。

## Mock 演示账号（密码均为 `demo1234`）

| 用户名 | 角色 | 主要页面 |
| --- | --- | --- |
| li.qian | 申请人 | 我的单据、编辑、详情、会话、报告 |
| zhou.shen | 审批人 | 工作台、审批任务、风险分析、金额核对 |
| li.caiwu | 财务 | 工作台、单据、风险/金额核对、供应商、规则 |
| chen.admin | 管理员 | 流程配置、审计日志、规则中心 |

## 目录

```text
src/
├── api/          # 域 API 模块 + client.ts（统一鉴权/幂等/错误处理）
├── components/   # StatusBadge、EvidenceDrawer、ApprovalDecisionDialog 等
├── mocks/        # 仅开发模式加载的 mock 数据与路由
├── router/       # 14 页路由 + 守卫（登录/角色）
├── stores/       # auth（token + principal）、app（toast）
├── styles/       # tokens.css（原型实测设计 token）+ base.css
├── types/        # status.ts（小写状态→中文/颜色映射）、domain.ts
├── utils/        # 字符串十进制金额（禁 float）、格式化
└── views/        # 14 个页面 + 403/404
```

## 约定

- 状态只保存/传输后端小写机器值，中文标签仅用于展示（SPEC 20 §3）。
- 金额为字符串 Decimal，两位小数 + 千分位展示，单币种 CNY（R-06）。
- 审批决定只走 `POST /api/v1/approval-tasks/{task_id}/decision`，弹窗内三种决定、意见必填、幂等键复用（SPEC 20 §4）。
- 401/403/404/409/422/503/500 统一在 `client.ts` 处理（SPEC 20 §7）。
- 开发模式下页面右上角的 API 路径提示（`ApiHint`）仅 `import.meta.env.DEV` 渲染，生产构建不出现。
- 后端就绪前，类型为按 SPEC 手写的契约类型；OpenAPI 固化后建议切换为生成类型（07-前端实施计划 任务 1）。
