# 费用报销单样板链路——模块级 SPEC

> 状态：已生成，待用户审核  
> 粒度：模块级；用于确认模块边界、数据结构、业务流程、代码文件分工和接口范围。  
> 实现前置：本 SPEC 审核通过后，再使用 `writing-plans` 拆分实现计划。

## 1. 文档说明

### 1.1 依据

- `财务评审文档/01-PRD/财务单据智能风险审核系统-PRD.md`
- `财务评审文档/02-概要设计/02-概要设计总纲.md`
- `财务评审文档/02-概要设计/05-数据对象文档.md`
- `财务评审文档/03-页面原型/02-费用报销单详情-风险复核.png`
- `财务评审文档/03-页面原型/01-财务审核工作台.png`

### 1.2 范围

本模块先打通费用报销单一条完整链路：草稿创建、附件上传、解析/OCR、规则分析、风险复核、审批人员决策和报告生成。其他 4 类单据复用本模块的单据版本、附件、分析、风险、审批和报告框架。

费用报销单不建立独立的第二套单据表或审批状态机。`/api/v1/expense-reimbursements` 仅作为样板链路门面路由，内部统一委托 `financial_documents`、`document_versions` 及对应应用服务；项目说明书规定的 `/api/v1/documents` 是通用单据资源的权威接口。

非目标：MVP 不实现会签/或签/加签/转审/委托、跨币种自动换算、AI 自动审批和外部模型默认调用。

## 2. 模块边界与代码分层

```text
Vue 页面/API
    ↓ OpenAPI
FastAPI router → application service → domain/rule service
                         ↓                  ↓
                   repository          OCR/LLM/RAG adapter
                         ↓                  ↓
                    PostgreSQL       Celery worker / Redis
                         ↓
                    FileStorage → 本地文件 / MinIO
```

| 层 | 职责 | 不负责 |
|---|---|---|
| `expense_reimbursement` router | 鉴权、参数校验、响应编排 | 风险计算、文件直接读写 |
| application service | 事务边界、版本创建、流程编排 | 供应商 SDK 细节 |
| domain/rule service | 单据校验、确定性风险规则、审批状态转换 | HTTP 细节 |
| repository | SQLAlchemy 查询和持久化 | 跨层业务决策 |
| Celery tasks | OCR、解析、分析、报告异步执行和重试 | 最终审批决定 |
| adapter | OCR、模型、RAG、FileStorage 外部能力 | 修改审批结果 |

## 3. 数据结构

### 3.1 参与表

| 表 | 用途 | 关键绑定 |
|---|---|---|
| `financial_documents` | 单据主记录 | `applicant_id`、`document_type=EXPENSE_REIMBURSEMENT` |
| `document_versions` | 每次提交/重提的不可变版本 | `document_id`、版本号、提交人 |
| `document_line_items` | 报销明细 | `document_version_id`、金额 `NUMERIC(18,2)` |
| `document_attachments` | 附件元数据 | `document_version_id`、FileStorage key |
| `attachment_parse_results` | OCR/解析结果 | `attachment_id`、原文和结构化字段 |
| `invoice_records` | 发票结构化信息 | `document_version_id`、发票号码/金额/日期 |
| `analysis_tasks` | 异步分析阶段状态 | `document_version_id`、阶段、重试/错误 |
| `risk_findings` | 规则风险项和证据 | `document_version_id`、证据定位、规则版本 |
| `manual_reviews` | 人工复核记录 | `risk_finding_id`、复核人、结论、意见、时间 |
| `approval_instances` / `approval_tasks` | 审批实例和待办 | `document_version_id`、审批人、任务状态 |
| `review_reports` | 最终报告 | `document_version_id`、综合风险等级 |
| `document_status_logs` / `audit_logs` | 状态和审计追踪 | 操作人、动作、时间、脱敏上下文 |

### 3.2 核心数据约束

- 金额使用 Python `Decimal` 和 PostgreSQL `NUMERIC(18,2)`；MVP 仅支持单币种。
- `document_version_id` 是附件、解析、分析、风险、审批和报告的强绑定键。
- 风险项至少保存：`finding_level`、`evidence_attachment_id`、页码/位置、`raw_snippet`、字段名、置信度、规则版本、分析时间；证据缺失时状态为“待人工确认”。
- 必需附件由单据类型附件矩阵配置，缺失时禁止提交。
- 单据编号由系统按类型、日期、流水号生成，不能由申请人覆盖。
- `document_line_items`、`document_attachments`、`attachment_parse_results`、`analysis_tasks`、`risk_findings`、`manual_reviews`、`approval_instances`、`review_reports` 必须同时保存 `document_version_id`；查询不得只按 `document_id` 读取当前版本。
- 草稿阶段的数据写入当前草稿；提交时将通用字段、`document_payload`、明细和附件清单固化为版本快照，提交后该版本内容不可更新。
- `review_sessions` / `session_messages` 仅承载多轮信息补齐和任务进度上下文，不作为单据、风险或审批结果的事实来源。

## 4. 业务流程

1. 申请人创建费用报销单草稿，系统生成 `document_no`。
2. 申请人填写核心字段和明细，上传附件；文件通过 `FileStorage` 保存，数据库只保存元数据。
3. 提交前校验权限、必填字段、金额精度、单币种和必需附件。
4. 提交时创建不可变 `document_version`，写入状态日志，创建解析/OCR/分析 Celery 任务。
5. Worker 依次执行解析、OCR、字段结构化、确定性规则检查；每阶段记录状态、重试次数、错误码和幂等键。
6. 证据完整的风险项进入风险复核；证据不足的风险项标记“待人工确认”。LLM 仅可补全字段、解释或提出建议。
7. 审批人员查看审批任务和风险证据，执行通过、退回或拒绝；最终决定写入 `approval_tasks`、`approval_instances` 和审计日志。
8. 退回重提创建新版本，从首个审批节点重新开始；旧版本和旧任务保留历史。
9. 审批完成后生成报告并绑定同一 `document_version_id`。

异常分支：外部 OCR/模型超时按策略重试；超过最大次数进入人工接管；重复提交由幂等键返回已有任务；越权查询返回 403 且写审计日志。

### 4.1 任务阶段与恢复边界

| 阶段 | 状态示例 | 成功后置动作 | 失败恢复 |
|---|---|---|---|
| 文件上传 | `uploading` / `stored` / `failed` | 写入附件元数据并校验哈希 | 可从上传阶段重试 |
| 解析/OCR | `queued` / `parsing` / `succeeded` / `failed` | 保存原文、字段、页码/坐标和置信度 | 从失败附件继续；不可恢复转人工 |
| 风险分析 | `analyzing` / `succeeded` / `failed` | 写入规则版本、风险项和证据引用 | 从分析阶段继续，不重复改写解析结果 |
| 报告生成 | `queued` / `running` / `succeeded` / `failed` | 生成绑定版本的报告 | 从报告阶段重试，历史报告不覆盖 |

每个阶段使用 `document_version_id + stage + idempotency_key` 保证幂等；任务重试必须保留错误码、错误信息、重试次数、开始/结束时间和 worker 记录。

## 5. 核心代码文件

以下为待创建的建议文件，最终以方法级 SPEC 和代码仓库结构为准：

参照 `sentiment_anlyse` 的 `app/`、`engines/`、`front/`、`test/`、`var/` 分层，建议使用：

```text
app/
├── routers/expense_reimbursement.py
├── schemas/expense_reimbursement.py
├── services/expense_reimbursement.py
└── exceptions/expense_reimbursement.py
engines/
├── contracts/expense_reimbursement.py
├── common/repositories.py
├── expense_reimbursement/          # 单据、版本、审批和规则领域逻辑
├── ocr/                            # OCR adapter
├── model/                          # LLM/RAG adapter
├── report_engine/                  # 报告生成
└── tasks/expense_reimbursement.py # Celery 任务
front/src/
├── views/expense-reimbursement/
├── api/expense-reimbursement.ts
├── types/expense-reimbursement.ts
└── components/risk-finding-list.vue
test/
├── app/expense_reimbursement/
└── engines/expense_reimbursement/
var/
├── uploads/                        # 本地 FileStorage 开发目录
└── logs/
```

生产环境 `var/uploads` 替换为 MinIO，业务代码只依赖 `FileStorage` 契约。

前端建议：

```text
frontend/src/views/
├── expense-reimbursement/ExpenseReimbursementEditView.vue
├── expense-reimbursement/ExpenseReimbursementDetailView.vue
├── review-workbench/ReviewWorkbenchView.vue
├── my-documents/MyDocumentsView.vue
├── approval-tasks/ApprovalTasksView.vue
├── rule-center/RuleCenterView.vue
└── report-center/ReportCenterView.vue
frontend/src/api/expense-reimbursement.ts
frontend/src/api/approval-tasks.ts
frontend/src/api/review-reports.ts
frontend/src/types/expense-reimbursement.ts
frontend/src/types/risk-finding.ts
frontend/src/components/risk-finding-list.vue
frontend/src/components/evidence-viewer.vue
frontend/src/components/approval-decision-dialog.vue
```

页面必须根据当前用户角色隐藏不可用操作；后端权限校验为最终边界。风险复核页必须同时展示风险状态、证据定位、人工复核入口和审批入口，不允许把 AI 建议渲染为最终审批结果。

## 6. 接口文档（模块范围）

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| `POST` | `/api/v1/expense-reimbursements` | 申请人 | 创建草稿并生成单据编号 |
| `GET` | `/api/v1/expense-reimbursements/{document_id}` | 数据范围 | 查询当前版本详情 |
| `POST` | `/api/v1/expense-reimbursements/{document_id}/attachments` | 申请人 | 上传附件并保存元数据 |
| `POST` | `/api/v1/expense-reimbursements/{document_id}/submit` | 申请人 | 校验并创建不可变版本 |
| `GET` | `/api/v1/expense-reimbursements/{document_id}/risk-findings` | 申请人/审批人/财务授权范围 | 查看风险及证据 |
| `GET` | `/api/v1/approval-tasks` | 审批人 | 查询分配给本人的任务 |
| `POST` | `/api/v1/approval-tasks/{task_id}/decision` | 当前审批人 | 通过、退回或拒绝 |
| `GET` | `/api/v1/review-reports/{document_version_id}` | 数据范围 | 查询审核报告 |

### 6.1 接口契约共性

统一要求：

- 写操作携带 `Idempotency-Key`；同一用户、同一业务动作和同一版本重复请求返回首次结果，不重复创建版本、任务或审批任务。
- 响应包含 `request_id`；异步操作返回 `task_id`、阶段状态和 `document_version_id`。
- 错误响应统一为 `{code, message, request_id, field_errors}`；至少使用 `VALIDATION_ERROR`（422）、`UNAUTHORIZED`（401）、`FORBIDDEN`（403）、`NOT_FOUND`（404）、`CONFLICT`（409）、`TASK_RETRYABLE`（503）。
- 所有查询执行 R-03 数据范围过滤；审批决定接口额外校验任务当前分配人和任务状态。
- 版本相关路径或请求体必须明确 `document_version_id`；禁止以“当前版本”替代历史版本读取。

### 6.2 主要请求/响应字段

| 接口 | 请求关键字段 | 成功响应关键字段 |
|---|---|---|
| 创建草稿 | `document_type`、费用报销专属 `document_payload`、`currency`、`apply_date` | `document_id`、`document_no`、`document_status=draft` |
| 上传附件 | `file`、`attachment_category`、`Idempotency-Key` | `attachment_id`、对象键、`storage_status`、`parse_status` |
| 提交 | `document_id`、`Idempotency-Key` | `document_version_id`、版本号、`task_id`、初始状态 |
| 风险复核 | `finding_id`、`review_result`、`review_comment`、证据确认信息 | `manual_review_id`、风险项最新人工状态、审计信息 |
| 审批决定 | `decision=approve/return/reject`、`comment`、`Idempotency-Key` | `task_id`、任务状态、实例状态、下一节点任务（如有） |

具体字段校验、枚举和响应示例由方法级 SPEC 固化；本模块 SPEC 只确认边界和契约必备字段。

## 7. 模块级验收标准

- [ ] 费用报销单可创建、保存、上传附件并提交。
- [ ] 缺少必需附件、跨币种、金额精度错误时不能提交。
- [ ] 每次提交/重提均产生不可变版本，旧版本可审计查看。
- [ ] OCR/分析任务可重试、恢复，失败超过阈值进入人工接管。
- [ ] 风险项可定位到附件、页码/位置和原文片段。
- [ ] AI 不能直接改变审批结果，审批人员决定通过/退回/拒绝。
- [ ] 申请人、审批人、财务和管理员无法越权读取数据。

## 8. 【重点审核】

1. 【已确认】模块边界足以支撑费用报销单首条垂直链路，一期只完整实现费用报销单，其他 4 类单据后续复用框架。
2. 【已确认】版本、证据、审批和报告全部绑定同一 `document_version_id`，历史版本保留且不可被新规则/模型改写。
3. 【已确认】接口权限按 R-03 执行：申请人仅本人，审批人仅分配任务，财务按授权组织范围，管理员主要管理配置且不默认查看全部业务数据。
4. 【已确认】Celery 按阶段记录状态、错误、重试和幂等键；超过上限进入人工接管，并支持从失败阶段恢复。
5. 【已确认】代码文件采用 `sentiment_anlyse` 的 `app/engines/front/test/var` 结构。

## 9. 单 Agent 工程化补充

- Agent Engine 负责会话读取、TurnPlan 校验、工具白名单调用和结果编排；不直接修改审批状态。
- Agent 工具注册和 Prompt 文件位于 `engines/contracts/`、`prompt/jinja2/`；审批使用固定顺序执行器，但节点来自管理员配置并发布的版本化模板。Agent 不得动态增删、跳过或重排节点，不引入动态 YAML 流程。
- 多步骤分析通过 SSE 返回 `progress`/`result` 事件；断线后通过任务状态恢复。
- 会话使用 `slot_state_json + state_version`，采用乐观锁和轮次事务提交。
- API、Agent、Celery 和工具调用通过 `request_id`、`agent_run_id`、`task_id`、`tool_call_id` 关联。
