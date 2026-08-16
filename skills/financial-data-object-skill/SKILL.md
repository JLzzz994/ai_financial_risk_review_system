---
name: financial-data-object-skill
description: 为当前财务单据智能风险审核系统生成或评审数据对象文档时使用。继承 `python-data-object-skill`，严格依据财务评审项目说明中的 25 张表、R-03/R-06/R-08/R-12/R-16 和已确认问答。
---

# Financial 数据对象设计

先读取 `财务评审文档/02-概要设计/05-数据对象文档.md` 和《财务风险评审项目说明.md》2.7.10 节。25 张既有表名必须保持一致：`users`、`roles`、`permissions`、`user_roles`、`role_permissions`、`review_sessions`、`session_messages`、`financial_documents`、`document_versions`、`document_line_items`、`document_attachments`、`attachment_parse_results`、`invoice_records`、`approval_workflows`、`approval_workflow_nodes`、`approval_instances`、`approval_tasks`、`document_status_logs`、`analysis_tasks`、`risk_findings`、`review_reports`、`market_price_references`、`supplier_profiles`、`manual_reviews`、`audit_logs`。

必须落实：

- Q-02：简化组织模型，用户保存组织、部门、职级和 `org_scope`。
- Q-03：核心字段结构化，扩展字段使用 `JSONB`，由接口层和规则引擎校验。
- Q-04：按单据类型配置必需附件，缺附件禁止提交。
- Q-05：单据编号由系统按类型、日期和流水号生成。
- Q-06：金额 `Decimal`/`NUMERIC(18,2)`，MVP 单币种，跨币种人工确认。
- Q-15：综合风险等级由确定性规则引擎按配置计算。
- R-08：风险证据字段完整可追溯；R-12：所有业务结果绑定不可变 `document_version_id`；R-16：文件内容进入 FileStorage/MinIO，数据库只保留元数据。

输出字段表时必须包含：表名、字段名、Python 类型、PostgreSQL 类型、必填、默认值、约束、来源和审核标记。未知内容集中列为待确认，不静默新增表。
