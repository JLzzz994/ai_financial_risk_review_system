---
name: python-coding-skill
description: 生成或评审通用 Python 后端、Vue 3 + TypeScript 前端、数据库访问和异步任务代码。涉及 FastAPI、Pydantic、SQLAlchemy、Alembic、PostgreSQL、Redis/Celery、外部服务适配层、OpenAPI 或前端页面/API 时使用；具体业务约束由项目专用技能补充。
---

# Python 编码规范 Skill

## 默认技术基线

- Python 3.12+，FastAPI + Pydantic v2，SQLAlchemy 2.x + Alembic。
- PostgreSQL；金额使用 `Decimal`，数据库使用 `NUMERIC(18,2)`。
- Redis + Celery 执行 OCR、解析、分析、报告等长耗时任务；任务必须幂等、可重试、可观测。
- Vue 3 + TypeScript，接口契约以 OpenAPI 为准。
- 外部服务通过独立适配器接入；业务层不得直接耦合具体供应商 SDK。

## 工作流

1. 先阅读 PRD、概要设计、数据对象文档、对应 SPEC 和现有代码。
2. 确认边界、权限、状态、版本号、证据链和异常分支；不凭空扩展业务规则。
3. 优先写可验证的测试，再实现最小变更；保持 API、数据库和前端字段一致。
4. 交付前运行测试、迁移检查、类型检查、OpenAPI 检查和中文乱码扫描。

## Python 后端规范

- 包和模块使用小写下划线；函数和变量使用 `snake_case`；类使用 `PascalCase`；常量使用 `UPPER_SNAKE_CASE`。
- FastAPI 路由只负责参数校验、鉴权和响应编排；业务规则放在 service/domain；数据库访问放在 repository/SQLAlchemy 层。
- Pydantic 请求/响应模型与 SQLAlchemy 持久化模型职责分离；只有字段完全一致且无边界风险时才复用。
- 依赖通过 FastAPI `Depends` 或显式构造注入；禁止在函数体内创建全局数据库连接、Redis 客户端或外部模型客户端。
- Decimal、日期时间和枚举保持明确类型；不把金额转成浮点数，不用字符串拼接 SQL。
- 所有外部调用设置超时、错误映射、重试上限和审计信息；禁止记录原始财务敏感数据。

## 异步任务规范

- 使用 `@celery_app.task` 注册任务，任务参数传递稳定 ID，不传递大文件和 ORM 实例。
- 任务按上传、解析、OCR、分析、报告阶段拆分；每阶段写状态、重试次数、错误码和幂等键。
- 重试使用指数退避和明确最大次数；不可恢复失败进入人工处理队列，不无限重试。
- 任务结果写入 PostgreSQL/对象存储，Redis 只保存短期状态或队列结果。

## 前端规范

- 页面位于 `frontend/src/views`，组件位于 `frontend/src/components`，API 位于 `frontend/src/api`，类型位于 `frontend/src/types`。
- 文件使用小写中划线；变量和函数使用 `camelCase`；类型和组件使用 `PascalCase`。
- 以 OpenAPI 生成或复用 TypeScript 类型；请求状态、错误、空状态、权限和分页必须有明确表现。
- 统一复用项目已有布局、表格、表单和提示组件，不重复造请求封装。

## 数据库规范

- 表名和字段使用小写下划线；所有表必须有 `id`、`created_at`、`updated_at`，需要时增加 `created_by`、`updated_by`、`is_deleted`。
- 外键、索引、唯一约束必须有数据对象文档或 SPEC 依据；不得为了“看起来完整”擅自添加。
- 业务版本、证据、审计等字段按目标项目的数据对象文档确定，不在通用层强加具体字段名。

## 交付检查

- `pytest`、`ruff check`、`mypy`（若项目启用）、Alembic 检查和前端类型检查通过。
- API 响应与 OpenAPI 一致；权限、日志、审计、幂等和异常路径可验证。
- 扫描新增文件，确保 UTF-8 中文正常，不出现 `浼`、`寰`、`鎵`、`鏄`、`锛`、`銆`、`�` 等乱码。
