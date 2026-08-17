# 报告管理与审计模块——模块级 SPEC

> 状态：已生成，待用户审核
>
> 范围：分析报告草稿、最终报告、报告查询、导出、版本绑定和操作审计。
>
> 【重点审核】两类报告接口关系、报告固化时机、历史不可变、导出权限和审计字段。

## 1. 模块目标与边界

本模块将风险分析结果、金额核对、供应商风险、证据和审批结果组织为可查询、可导出的报告，并记录系统操作审计。报告不重新计算风险，也不替代审批决定。

包含：

- 分析阶段报告草稿生成和查询；
- 最终审批通过后的报告固化；
- 按不可变单据版本查询报告；
- 按分析任务查询报告投影；
- PDF/Excel 等导出任务和下载；
- 登录、单据、附件、规则、分析、复核、审批和报告操作审计。

不包含：风险规则计算、审批决定、附件解析和用户权限维护。

## 2. 报告生命周期

报告状态统一使用小写：`draft`、`final`、`failed`。

1. 分析任务成功后生成绑定版本的 `draft` 报告，供人工复核和审批查看。
2. 最终审批决定成功提交后，事务内将报告固化为 `final`；只有审批状态机确认通过的决定才允许固化。退回或驳回不生成最终报告，但保留草稿和历史意见。旧 `approve`/`return`/`reject` 路径仅作为兼容网关说明，不能绕过正式审批决定接口。
3. 正式报告必须绑定 `document_version_id`、`analysis_task_id` 和规则/模型版本；历史报告不可修改或覆盖，正式报告只能固化一次。
4. 新版本重新生成新报告，不影响旧版本报告。

## 3. 两类报告接口关系

| 接口 | 视角 | 权威性 | 用途 |
|---|---|---|---|
| `GET /api/v1/analysis-tasks/{task_id}/report` | 分析任务视角 | 返回任务报告投影 | 查询任务状态关联的草稿/最终报告、面板数据和 `review_report_id` |
| `GET /api/v1/review-reports/{document_version_id}` | 不可变版本视角 | 正式报告权威来源 | 审计、历史查询、导出和版本追溯 |

任务报告接口必须返回 `document_version_id` 和 `review_report_id`，不得独立生成第二份事实。版本报告接口是导出和审计的唯一事实来源。

## 4. 报告内容

- 整体风险等级和高/中/低风险数量；
- 金额核对：单据总金额、明细合计、发票合计、合同金额、付款金额和差异；
- 风险项：类型、等级、描述、实际值、参考值、阈值、处理建议和复核状态；
- 供应商风险：标签、黑名单、历史异常、账号变化；
- 证据索引：附件、页码/坐标、原文片段和字段路径；
- 审批进度、审批意见和最终决定；
- 规则版本、模型元数据、分析时间和报告生成时间。

## 5. 审计要求

`audit_logs` 只追加，至少保留 3 年，记录：`actor_id`、动作、资源类型、资源 ID、请求 ID、客户端 IP、User-Agent、结果、失败原因、变更前后摘要和时间。到期后按归档策略处理，不直接物理删除。不得记录密码、完整 Token、银行卡号、身份证号、附件原文或完整 Prompt。

敏感操作必须审计：登录、权限拒绝、单据状态变化、附件访问/删除、规则发布、分析任务、风险复核、审批决定、报告生成和导出。

## 6. 核心代码文件

```text
app/
├── routers/reports.py
├── routers/audit_logs.py
├── schemas/reports.py
├── services/report_service.py
└── services/audit_service.py
engines/
├── report/report_builder.py
├── report/report_exporter.py
├── report/report_version_guard.py
└── audit/audit_writer.py
workers/
└── report_tasks.py
front/src/
├── views/reports/ReportDetailView.vue
├── views/reports/ReportExportView.vue
├── views/audit/AuditLogView.vue
└── api/reports.ts
test/
├── app/reports/test_report_router.py
├── engines/report/test_report_builder.py
└── engines/audit/test_audit_writer.py
```

## 7. 接口范围

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| `GET` | `/api/v1/analysis-tasks/{task_id}/report` | 数据范围 | 查询分析任务报告投影 |
| `GET` | `/api/v1/review-reports/{document_version_id}` | 数据范围 | 查询版本权威报告 |
| `POST` | `/api/v1/review-reports/{document_version_id}/export` | 数据范围 | 创建报告导出任务 |
| `GET` | `/api/v1/review-reports/{report_id}/export` | 数据范围 | 项目说明兼容导出入口，转发到版本报告导出 Service |
| `POST` | `/api/v1/review-reports/{report_id}/manual-reviews` | 授权审核人员 | 项目说明兼容入口，仅提交人工复核意见；最终审批仍必须调用 `/approval-tasks/{task_id}/decision` |
| `GET` | `/api/v1/review-reports/exports/{export_task_id}` | 创建人/数据范围 | 查询导出状态 |
| `GET` | `/api/v1/review-reports/exports/{export_task_id}/download` | 创建人/数据范围 | 下载导出文件 |
| `GET` | `/api/v1/audit-logs` | `audit:read` | 查询审计日志 |

## 8. 验收标准

- [ ] 分析成功生成版本绑定的 `draft` 报告。
- [ ] 只有正式审批决定成功后才能固化 `final` 报告，且正式报告只能固化一次。
- [ ] 两类报告接口返回同一事实链，不生成冲突数据。
- [ ] 历史版本报告只读，新版本不覆盖旧报告。
- [ ] 报告包含风险、金额、供应商、证据、审批和版本信息。
- [ ] 报告导出异步执行，支持状态查询和权限下载；导出记录版本、权限、`request_id` 和审计事件。
- [ ] 导出文件在对象存储保留 24 小时，下载链接有效期 5 分钟；过期清理失败可重试，任务和审计记录保留。
- [ ] 敏感操作写入完整脱敏审计日志。

## 9. 【重点审核】

1. 报告草稿和最终报告的生成时机。
2. 两类报告接口的权威关系。
3. 报告导出格式和有效期。
4. 审计日志查询范围和至少 3 年的保留期限。
