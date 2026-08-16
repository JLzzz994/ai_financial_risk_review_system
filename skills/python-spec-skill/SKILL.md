---
name: python-spec-skill
description: 基于 PRD、Python 模块概要设计和数据对象文档，生成或评审可直接编码的通用模块级 SPEC。涉及 FastAPI 路由、Pydantic schema、SQLAlchemy/Alembic、Celery 任务、Vue 3 页面、TypeScript API、OpenAPI、权限、日志或验收时使用。
---

# Python 模块 SPEC Skill

## 输入与顺序

先读取 PRD、概要设计总纲、目标模块概要设计、数据对象文档、原型和现有代码。确认单据版本、权限、状态、证据、重试和人工审批规则后再写 SPEC。

## 文档结构

1. 文档说明、范围、依据和非目标
2. 模块概览与上下游依赖
3. 精确目录与文件清单（新增/修改到文件级）
4. 数据对象与迁移：SQLAlchemy 模型、Pydantic schema、Alembic revision、字段和约束；不复制完整 SQL，除非项目明确要求
5. 后端设计：router、service、repository、domain、Celery task 的类/函数签名、校验、事务、幂等、异常和返回值
6. 前端设计：Vue 页面、组件、状态、表单/表格、API 方法、类型和交互状态
7. OpenAPI 接口契约：方法、路径、权限、请求/响应示例、错误码和分页
8. 异步与适配器：Celery 队列、重试策略、OCR/LLM/RAG adapter、FileStorage/MinIO
9. 权限、审计与日志：数据范围、关键事件、脱敏规则
10. 测试与验收：pytest、API、任务、迁移、前端和可验证 checkbox
11. 待确认项和【重点审核】项

## 关键实现约束

- 参数超过 5 个时定义 Pydantic command/query schema；不把 ORM 对象直接作为 API 响应。
- 金额使用 Decimal；响应和 OpenAPI 明确金额字符串/数字的序列化约定。
- Celery 任务只传 ID 和幂等键；每个阶段记录状态、重试、错误和人工接管。
- 风险规则由确定性引擎计算；LLM 只能补全、解释或建议；审批人员决定最终审批结果。
- 业务结论的证据和版本绑定按项目数据对象文档定义。
- 文件通过项目约定的存储抽象访问，不在通用层指定具体供应商。
- 接口、数据库、前端类型和验收标准必须逐项对齐；禁止 `xxx`、`TODO`、`待补充` 等占位符。

## 交付检查

- 文件、模块、函数、接口和权限标识均可定位。
- 正常、校验失败、重复提交、外部服务失败、重试耗尽和人工接管均有处理。
- `pytest`、迁移检查、OpenAPI 生成/校验、前端类型检查和乱码扫描命令明确。
- 生成图示时调用 `diagram-builder`；形成实施计划时调用 `writing-plans`，计划必须引用本 SPEC 的真实文件路径。
