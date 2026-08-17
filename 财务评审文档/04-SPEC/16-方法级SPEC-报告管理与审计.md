# 报告管理与审计模块——方法级 SPEC

> 状态：已生成，待用户审核
>
> 【重点审核】报告草稿/最终固化、接口投影关系、导出幂等、历史不可变和审计写入。

## 1. 方法清单

| 方法 | 文件 | 职责 |
|---|---|---|
| `build_draft_report` | `app/services/report_service.py` | 分析完成后生成草稿 |
| `get_task_report_projection` | `app/services/report_service.py` | 返回任务视角报告投影 |
| `get_version_report` | `app/services/report_service.py` | 返回版本权威报告 |
| `finalize_report` | `app/services/report_service.py` | 最终审批通过后固化报告 |
| `create_export_task` | `app/services/report_service.py` | 创建异步导出任务 |
| `write_audit_log` | `engines/audit/audit_writer.py` | 脱敏写入追加审计 |
| `query_audit_logs` | `app/services/audit_service.py` | 按权限查询审计 |

## 2. `build_draft_report`

读取指定 `document_version_id` 的风险项、金额核对、供应商风险、证据、人工复核和审批进度，生成 `draft` 报告。只读引用业务事实，不重新计算规则；同一版本和分析任务重复调用返回同一报告。

## 3. 两类查询方法

`get_task_report_projection(task_id)` 先查询任务绑定的 `document_version_id` 和 `review_report_id`，再调用 `get_version_report(document_version_id)` 组装任务状态、当前步骤和报告内容。禁止复制生成第二份风险或金额事实。

`get_version_report(document_version_id)` 只返回用户数据权限范围内、版本绑定的报告；历史版本可查询但不可修改。

## 4. `finalize_report`

1. 校验正式审批决定事务由当前审批人员成功提交且实例状态为 `approved`；旧审批路径只能由兼容网关转发，不得直接固化报告；
2. 锁定版本的 `draft` 报告；
3. 固化为 `final`，写入最终审批人、时间和报告版本；
4. 写入审计日志；
5. 事务提交后通知导出和前端刷新。

最终报告只允许固化一次；重复调用返回已有 `final` 报告，不能覆盖。

## 5. `create_export_task`

- 支持 PDF 和 XLSX 两种格式；
- 导出内容来自版本权威报告，不从任务投影单独生成；
- 使用 `document_version_id + report_id + format + idempotency_key` 幂等；调用方必须提供 `Idempotency-Key`，导出记录保存权限决策、版本、`request_id` 和审计事件；
- 通过 Celery 异步生成，状态 `queued`/`running`/`succeeded`/`failed`；
- 导出文件使用 MinIO/FileStorage 保存，下载链接默认 5 分钟有效；
- 导出文件默认保留 24 小时，过期后清理对象但保留任务和审计记录；清理失败进入后台重试；
- 任务失败保留错误并支持重试。

## 6. `write_audit_log` 与 `query_audit_logs`

审计写入与关键业务事务使用同一事务，确保状态变化和审计记录同时成功或回滚。日志至少保留 3 年，到期后进入归档流程。查询只返回当前用户被授予的审计范围；普通业务用户不能查询全局审计，管理员需具备 `audit:read`。

## 7. 测试用例

- 分析成功生成草稿，最终审批通过只固化一次最终报告。
- 任务报告投影和版本报告内容一致，并返回相同报告 ID。
- 历史版本报告只读，新版本不覆盖旧报告。
- PDF/XLSX 导出异步、幂等、可重试和短期下载；导出记录包含权限、版本、`request_id` 和审计事件。
- 无数据权限用户不能查看、导出或下载报告。
- 审计事务一致、敏感字段脱敏、普通用户不能查询全局审计。
