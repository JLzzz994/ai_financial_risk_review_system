---
name: python-outline-design-skill
description: 生成或评审 Python 技术栈的模块概要设计。适用于已有 PRD、数据对象、原型或代码，需要梳理 FastAPI、Celery、Vue、权限、流程、接口、日志和验收范围时；不输出代码、SQL 或伪代码。
---

# Python 模块概要设计 Skill

## 输入

优先读取 PRD、概要设计总纲、数据对象文档、页面原型、接口和现有实现。输入不足时写明假设和待确认项。

## 文档结构

1. 文档说明：目的、范围、依据和非目标
2. 模块边界：FastAPI router、service、repository、domain、Celery tasks、Vue 页面/API 的职责及上下游
3. 核心流程：正常、失败、重试、人工接管和审批分支
4. 数据设计：对象、版本、状态、权限、证据链和对象存储元数据
5. 后端设计：目录、依赖方向、校验、事务和异步任务编排
6. 前端设计：页面区域、字段、交互、加载/空/错误状态和 API
7. 接口设计：路径、参数、响应、错误和权限
8. 权限与日志：R-03 数据范围、审计事件、敏感信息脱敏
9. 验收标准：按功能、异常、权限、异步任务和日志写可验证 checkbox

## 关键约束

- 技术栈固定为 Python 3.12+、FastAPI、PostgreSQL、Redis/Celery、Vue 3、TypeScript、OpenAPI。
- 外部能力只通过 adapter 接口调用；业务决策边界由项目需求定义。
- 说明事务边界、幂等键、重试节点和失败恢复，不把 Celery 当作数据库事务。
- 流程图、架构图、状态机或 ER 图交给 `diagram-builder`/`excalidraw-diagram` 生成并渲染验证。
- 概要设计不写实现代码、SQL 或伪代码；所有不确定命名集中列为待确认项。
