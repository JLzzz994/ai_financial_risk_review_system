---
name: financial-spec-skill
description: 为当前财务单据智能风险审核系统生成或评审模块级 SPEC 时使用。继承 `python-spec-skill`，将费用报销单样板链路、25 张表、OpenAPI、Celery、OCR/LLM 适配层、权限、证据链、版本和 MinIO 细化到可编码文件与验收项。
---

# Financial 模块 SPEC

先读取目标模块概要设计、PRD、数据对象文档、原型和当前项目已确认决策。SPEC 必须精确到文件级，至少说明：

- 后端：FastAPI 路由、Pydantic schema、SQLAlchemy 模型/Repository、Service、Celery task、Alembic revision、FileStorage/MinIO adapter。
- 前端：工作台、我的单据、审批任务、规则中心、报告中心和费用报销单风险复核页面的 Vue/TypeScript 文件、状态、API 和权限。
- 接口：OpenAPI 方法、路径、请求/响应、错误码、幂等键、数据范围和审批人员决策入口。
- 业务：只先实现费用报销单垂直链路；其他 4 类复用框架；AI 只辅助，最终由审批人员决定。
- 证据：风险项绑定附件、页码/位置、原文、字段、置信度、规则版本、分析时间；缺证据为人工确认。
- 异步：上传/解析/OCR/分析/报告任务的状态、重试、恢复、超时、幂等和人工接管。
- 验收：正常、校验失败、重复提交、退回重提、版本隔离、权限越权、外部服务失败和审计日志。

生成架构/流程/状态/ER 图时调用 `diagram-builder`；SPEC 审核通过后调用 `writing-plans`，计划必须逐项引用真实文件、测试命令和预期结果。禁止 Java、Spring、MyBatis、MySQL 术语和未经确认的业务字段。
