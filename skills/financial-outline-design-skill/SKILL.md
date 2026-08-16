---
name: financial-outline-design-skill
description: 为当前财务单据智能风险审核系统生成或评审模块概要设计时使用。继承 `python-outline-design-skill`，将 R-01～R-17、5 类单据、费用报销单样板链路和审批人员最终决策落到模块边界、流程、权限和验收。
---

# Financial 模块概要设计

依据 PRD、`02-概要设计/02-概要设计总纲.md`、`05-数据对象文档.md` 和 6 个统一风格原型页面编写。必须覆盖：

- 模块边界：FastAPI router/service/repository/domain、Celery tasks、OCR/LLM/RAG adapter、Vue 页面/API。
- 样板链路：费用报销单上传 → 解析/OCR → 规则分析 → 风险复核 → 审批人员最终决定 → 报告。
- 权限：申请人仅看本人单据，审批人只看分配任务，财务按授权组织范围查看，管理员主要维护配置。
- 版本与状态：提交/重新提交生成不可变版本；退回重提从首个审批节点开始，旧任务保留历史。
- 风险边界：AI 不直接审批；确定性规则输出风险，证据不足进入人工确认。
- 异步边界：Celery 阶段状态、重试、恢复、错误和人工接管。

流程图、架构图、状态机和 ER 图交给 `diagram-builder` 生成，并在概要设计中引用图文件和审核重点。不要输出代码、SQL 或伪代码。
