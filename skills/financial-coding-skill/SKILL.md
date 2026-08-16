---
name: financial-coding-skill
description: 为当前财务单据智能风险审核系统生成或评审代码时使用。继承 `python-coding-skill`，并强制执行本项目 R-01～R-17、5 类财务单据、人工最终审批、风险证据链、FileStorage/MinIO 和 FastAPI/Celery 约束。
---

# Financial 项目编码约束

先读取：

- `财务评审文档/01-PRD/财务单据智能风险审核系统-PRD.md`
- `财务评审文档/02-概要设计/02-概要设计总纲.md`
- `财务评审文档/02-概要设计/05-数据对象文档.md`
- 目标模块 SPEC 和相关原型

在通用 `python-coding-skill` 之上执行：

- 技术栈固定为 Python 3.12+、FastAPI、PostgreSQL、Redis/Celery、Vue 3、TypeScript、OpenAPI。
- R-01 先打通费用报销单；R-02 最终审批/退回/拒绝由审批人员决定，AI 只能辅助。
- R-07 确定性规则引擎负责风险结论；LLM 只做字段补全、解释和建议；Agent 只编排工具；RAG 只检索制度/规则。
- R-08 每条风险必须绑定附件、页码/位置、原文片段、字段、置信度、规则版本和分析时间；证据缺失必须为“待人工确认”。
- R-11 上传、解析、OCR、分析、报告阶段使用 Celery，任务可重试、可恢复、可人工接管。
- R-12 每次提交/重新提交生成不可变 `document_version`，审批、附件、分析和报告必须绑定同一版本。
- R-16 使用 `FileStorage` 抽象；本地开发使用本地文件，生产使用 MinIO。
- 金额使用 Python `Decimal`，数据库使用 `NUMERIC(18,2)`；MVP 单币种，禁止隐式汇率换算。

交付前必须验证权限数据范围、版本绑定、幂等/重试、审计脱敏、OpenAPI 和中文乱码。
