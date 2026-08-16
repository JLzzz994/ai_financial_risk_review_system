# 费用报销单样板链路——方法级 SPEC

> 路由说明：费用报销门面路由与项目说明书中的通用 `/api/v1/documents` 路由调用同一应用服务和数据模型，不复制业务状态机。

> 状态：已生成，待用户审核  
> 粒度：方法级；把模块级边界拆到可编码的方法、输入输出、事务、任务、接口和验收用例。  
> 依据：PRD、概要设计总纲、`05-数据对象文档.md`、`01-模块级SPEC-费用报销单样板链路.md` 及 R-01～R-17。  
> 约束：本文件不替代模块级 SPEC；两者冲突时，以用户审核后的模块级 SPEC 为准。MVP 只实现费用报销单，其他 4 类单据复用框架。

## 1. 方法清单与调用关系

分析和审批必须是两个阶段：分析阶段生成可供人工复核的报告草稿；最终审批通过后再固化最终报告。AI/LLM 不得调用审批决定方法。

```text
create_expense_reimbursement
  ├─ upload_attachment (0..N)
  └─ submit_expense_reimbursement
       ├─ create_document_version
       ├─ create_approval_instance
       └─ enqueue_parse_pipeline
            ├─ parse_attachment_task (per attachment)
            │    └─ run_ocr_task
            ├─ extract_fields_task
            ├─ evaluate_risk_task
            └─ build_review_report_task (草稿)

approval_task_decision
  ├─ return → resubmit_expense_reimbursement → 新版本并回到首节点
  ├─ reject → close_rejected_version
  └─ approve → finalize_review_report
```

| 方法 | 所属文件 | 事务/队列 | 结果 |
|---|---|---|---|
| `create_expense_reimbursement` | `service.py` | DB 事务 | 草稿和系统生成的 `document_no` |
| `upload_attachment` | `service.py` + `adapters/storage.py` | 对象存储 + DB 事务 | 附件元数据 |
| `submit_expense_reimbursement` | `service.py` | DB 事务；提交后投递 Celery | 版本、审批实例和任务 ID |
| `create_document_version` | `version_service.py` | 同一 DB 事务 | 不可变版本快照 |
| `enqueue_parse_pipeline` | `tasks.py` | Celery/Redis | 阶段任务记录 |
| `parse_attachment_task` | `tasks.py` | Celery | 解析结果 |
| `run_ocr_task` | `tasks.py` + `adapters/ocr.py` | Celery | OCR 原文和定位 |
| `extract_fields_task` | `tasks.py` + `adapters/model.py` | Celery | 结构化字段和发票记录 |
| `evaluate_risk_rules` | `rules.py` | Celery 内同步调用 | 风险项和证据 |
| `build_review_report_task` | `tasks.py` | Celery | 可供复核的报告草稿 |
| `decide_approval_task` | `service.py` | DB 事务 | 人工审批结果和状态 |
| `finalize_review_report` | `report_service.py` | DB 事务 | 审批结果绑定后的最终报告 |

## 2. 方法级数据结构

### 2.1 公共类型

```python
class ActorContext(TypedDict):
    user_id: UUID
    roles: list[str]
    organization_ids: list[UUID]

class ExpenseLineItemCreate(BaseModel):
    expense_category: str = Field(min_length=1, max_length=64)
    expense_date: date
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(ge=Decimal("0.00"))

class ExpenseReimbursementCreate(BaseModel):
    apply_date: date
    department_id: UUID
    reason_text: str = Field(min_length=1, max_length=2000)
    currency: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")
    total_amount: Decimal = Field(ge=Decimal("0.00"))
    line_items: list[ExpenseLineItemCreate] = Field(min_length=1)
    document_payload: dict[str, Any] = Field(default_factory=dict)
```

金额校验使用 Python `Decimal`，精度固定为 2 位；`total_amount` 必须等于明细合计，数据库字段为 `NUMERIC(18,2)`。`document_type` 固定为 `EXPENSE_REIMBURSEMENT`，核心字段写入 `financial_documents`，扩展字段写入 `document_payload JSONB`。

### 2.2 提交、版本和幂等

```python
class SubmitExpenseReimbursementCommand(BaseModel):
    document_id: UUID
    expected_document_updated_at: datetime | None = None
    idempotency_key: str = Field(min_length=16, max_length=128)

class SubmissionView(BaseModel):
    document_id: UUID
    document_version_id: UUID
    approval_instance_id: UUID
    analysis_task_id: UUID
    status: Literal["pending_review", "reviewing"]
```

同一用户、同一路径和同一 `Idempotency-Key` 在有效期内只能成功一次；重复请求返回第一次结果，不重复创建版本、审批实例或 Celery 任务。`expected_document_updated_at` 不匹配时返回版本冲突。

### 2.3 附件、风险证据和审批

```python
class AttachmentView(BaseModel):
    attachment_id: UUID
    document_version_id: UUID | None
    file_name: str
    mime_type: Literal["application/pdf", "image/png", "image/jpeg"]
    sha256: str
    size_bytes: int
    storage_status: Literal["uploading", "stored", "failed"]

class RiskFindingEvidence(BaseModel):
    attachment_id: UUID
    page_no: int | None = Field(default=None, ge=1)
    position: dict[str, int] | None = None
    raw_snippet: str | None = None
    field_name: str | None = None
    confidence: Decimal | None = Field(default=None, ge=Decimal("0.0000"), le=Decimal("1.0000"))
    rule_version: str = Field(min_length=1, max_length=64)
    analyzed_at: datetime

class ApprovalDecisionCommand(BaseModel):
    decision: Literal["approve", "return", "reject"]
    comment: str | None = Field(default=None, max_length=2000)
    idempotency_key: str = Field(min_length=16, max_length=128)
```

已确认风险必须包含附件、页码或位置、原文片段、字段名、置信度、规则版本和分析时间；若任一必要证据缺失，风险项的处理状态必须为 `PENDING_MANUAL_CONFIRMATION`，不得当作已确认结论参与自动化放行。证据模型中的可空字段仅用于表示“待人工确认”，持久化前由校验器强制执行该规则。

## 3. 方法级业务流程与约束

### 3.1 `create_expense_reimbursement`

签名：`create_expense_reimbursement(command: ExpenseReimbursementCreate, actor: ActorContext) -> ExpenseReimbursementView`

1. 校验 actor 具有申请权限，且 `department_id` 在其可申请组织范围内。
2. 校验日期、币种、金额 2 位小数和明细合计。
3. 在同一事务中生成唯一 `document_no`，写入 `financial_documents`（`draft`）和 `document_line_items`。
4. 写入 `document_status_logs` 和 `audit_logs`，不记录密码、凭据或完整敏感账号。

失败：字段错误 `422 VALIDATION_ERROR`；组织越权 `403 DATA_SCOPE_DENIED`；编号唯一冲突由服务端重试，超过重试上限返回 `409 DOCUMENT_NO_GENERATION_FAILED`。

### 3.2 `upload_attachment`

签名：`upload_attachment(document_id: UUID, upload: UploadFile, actor: ActorContext) -> AttachmentView`

1. 校验单据归属、数据范围和当前单据仍为 `draft` 或 `returned`；附件上传阶段不绑定不可变版本。
2. 校验扩展名与 MIME、大小、页数及病毒扫描结果；首期只允许 PDF、PNG、JPG。
3. 调用 `FileStorage.put(stream, object_key, metadata)`；数据库只保存 object key、hash、大小、MIME 和页数，不暴露物理路径。
4. 存储成功后在同一 DB 事务写入 `document_attachments` 和审计日志；DB 失败时删除刚写入的对象或标记待清理，禁止留下可见的无效附件记录。

### 3.3 `submit_expense_reimbursement` / `create_document_version`

签名：

```python
submit_expense_reimbursement(
    command: SubmitExpenseReimbursementCommand,
    actor: ActorContext,
) -> SubmissionView
create_document_version(
    document_id: UUID,
    submitted_by: UUID,
    expected_updated_at: datetime | None,
) -> DocumentVersionView
```

1. 获取 Redis 幂等锁并校验草稿或退回状态。
2. 校验必填字段、附件矩阵、同币种和金额精度；缺少必需附件时禁止提交。
3. 在同一 DB 事务创建不可变 `document_versions` 快照，并将明细、附件及专属字段绑定到该版本。
4. 创建匹配的 `approval_instances` 和首节点 `approval_tasks`，状态写入 `pending_review`/`reviewing`。
5. 事务提交成功后再投递 `enqueue_parse_pipeline`，失败时记录可重试错误，不能产生“数据库有任务但队列无任务”的无审计状态。

### 3.4 异步解析与分析方法

所有 Celery 任务只接收 ID、幂等键和版本号，不传文件二进制或 ORM 对象。每个阶段在 `analysis_tasks` 记录 `queued/running/succeeded/failed/manual_review`、开始/结束时间、重试次数、错误码和幂等键；重试从失败节点继续，不默认重跑整链路。

```python
enqueue_parse_pipeline(document_version_id: UUID, idempotency_key: str) -> AnalysisTaskView
parse_attachment_task(attachment_id: UUID, document_version_id: UUID, idempotency_key: str) -> None
run_ocr_task(attachment_id: UUID, document_version_id: UUID, idempotency_key: str) -> None
extract_fields_task(document_version_id: UUID, idempotency_key: str) -> None
evaluate_risk_task(document_version_id: UUID, idempotency_key: str) -> None
build_review_report_task(document_version_id: UUID, idempotency_key: str) -> None
```

- `run_ocr_task` 通过 `OcrAdapter` 获取原文、页码和坐标；私有化服务优先，外部调用须经过脱敏和授权。
- `extract_fields_task` 通过独立适配层生成结构化字段和 `invoice_records`；LLM 只能补全、解释或建议，不能写入审批结论。
- `evaluate_risk_rules(document_version_id: UUID, context: RuleContext) -> list[RiskFindingDraft]` 只执行确定性规则，生成绑定版本的风险项和证据。
- 规则计算综合风险等级，不能由 LLM 覆盖；证据不完整则为人工确认。
- `build_review_report_task` 生成绑定版本的报告草稿；不可恢复失败转人工接管并保留错误原因。

### 3.5 `decide_approval_task` / 退回重提

签名：`decide_approval_task(task_id: UUID, command: ApprovalDecisionCommand, actor: ActorContext) -> ApprovalTaskView`

1. 校验任务属于当前审批人、任务状态为 `pending`，并按 R-03 执行数据范围过滤。
2. 校验当前任务绑定的 `document_version_id`；同一幂等键或已处理任务返回一致结果，不重复推进流程。
3. `approve`：完成当前任务；有下一顺序节点则创建下一任务，最终节点才进入报告固化。
4. `return`：关闭当前版本的未完成任务并保留意见；申请人重提时必须创建新版本并回到首节点，旧版本、任务和意见只读保留。
5. `reject`：终止当前版本审批，保留审批意见和审计记录。
6. 所有结果写入 `approval_tasks`、`approval_instances`、`document_status_logs` 和 `audit_logs`；AI/LLM/Agent 无权调用此方法模拟审批人。

签名：`finalize_review_report(document_version_id: UUID, approved_by: UUID) -> ReviewReportView`。仅最终审批通过事务成功后调用，报告绑定同一版本，不覆盖历史报告。

## 4. 核心代码文件与方法签名

```text
backend/app/modules/expense_reimbursement/
├── router.py
│   ├── create_expense_reimbursement
│   ├── upload_attachment
│   ├── submit_expense_reimbursement
│   └── decide_approval_task
├── schemas.py
│   ├── ExpenseReimbursementCreate
│   ├── SubmitExpenseReimbursementCommand
│   ├── ApprovalDecisionCommand
│   └── ExpenseReimbursementView / SubmissionView / RiskFindingView
├── models.py                 # SQLAlchemy 对应数据对象文档表
├── repository.py             # 版本、附件、风险、审批任务的查询和持久化
├── service.py                # 创建、上传、提交、审批事务编排
├── version_service.py        # 不可变版本和退回重提
├── report_service.py         # 报告草稿查询和最终固化
├── rules.py                  # 确定性报销风险规则
├── tasks.py                  # Celery 任务、重试和人工接管
├── adapters/
│   ├── ocr.py                # OcrAdapter
│   ├── model.py              # LlmAdapter（仅补全/解释/建议）
│   └── storage.py            # FileStorage；本地实现/MinIO 实现
├── migrations/versions/      # Alembic revision
└── tests/
    ├── test_service.py
    ├── test_version_service.py
    ├── test_rules.py
    ├── test_api.py
    └── test_tasks.py

frontend/src/
├── api/expense-reimbursement.ts
├── types/expense-reimbursement.ts
├── views/expense-reimbursement/ExpenseReimbursementDetail.vue
└── components/risk-finding-list.vue
```

## 5. 方法级接口文档

所有接口返回 `request_id`，查询接口执行 R-03 数据范围过滤；写接口使用 `Idempotency-Key`，错误统一为 `{"code", "message", "request_id", "field_errors"}`。

| 方法 | 路径 | 权限 | 成功响应 | 主要错误 |
|---|---|---|---|---|
| `POST` | `/api/v1/expense-reimbursements` | 申请人 | `201 ExpenseReimbursementView` | `VALIDATION_ERROR`、`DATA_SCOPE_DENIED` |
| `POST` | `/api/v1/expense-reimbursements/{document_id}/attachments` | 申请人 | `201 AttachmentView` | `DOCUMENT_NOT_EDITABLE`、`UNSUPPORTED_FILE_TYPE`、`FILE_TOO_LARGE`、`STORAGE_WRITE_FAILED` |
| `POST` | `/api/v1/expense-reimbursements/{document_id}/submit` | 申请人 | `202 SubmissionView` | `REQUIRED_ATTACHMENT_MISSING`、`CURRENCY_NOT_SUPPORTED`、`VERSION_CONFLICT`、`IDEMPOTENCY_CONFLICT` |
| `GET` | `/api/v1/expense-reimbursements/{document_id}/risk-findings?version_id={uuid}` | 申请人/当前审批人/授权财务 | `200 list[RiskFindingView]` | `DATA_SCOPE_DENIED`、`VERSION_NOT_FOUND` |
| `POST` | `/api/v1/approval-tasks/{task_id}/decision` | 当前审批人 | `200 ApprovalTaskView` | `TASK_NOT_ASSIGNED`、`TASK_ALREADY_PROCESSED`、`EVIDENCE_PENDING_MANUAL_CONFIRMATION`、`IDEMPOTENCY_CONFLICT` |
| `GET` | `/api/v1/analysis-tasks/{task_id}/report` | 数据范围 | `200 AnalysisTaskReportView` | `TASK_NOT_FOUND`、`REPORT_NOT_READY` |
| `GET` | `/api/v1/review-reports/{document_version_id}` | 数据范围 | `200 ReviewReportView`（草稿/最终） | `DATA_SCOPE_DENIED`、`REPORT_NOT_READY` |

两类报告接口返回同一事实链：分析任务接口是任务视角的报告投影，必须带回 `document_version_id` 和 `review_report_id`；版本报告接口是指定不可变版本的权威报告，用于审计、导出和历史追溯。任务接口不得生成脱离 `review_reports` 的第二份报告。

`EVIDENCE_PENDING_MANUAL_CONFIRMATION` 是否阻止审批、以及审批人员是否可选择“带风险处理”，属于用户待审核项；实现默认阻止自动放行，但不替审批人员做最终决定。

## 6. 方法级测试与验收

- [ ] `create_expense_reimbursement` 校验申请人组织范围、明细合计、金额精度和单据编号唯一性。
- [ ] `upload_attachment` 校验类型/大小/病毒扫描；FileStorage 失败不留下可见的无效记录。
- [ ] 提交缺少必需附件、跨币种或并发版本冲突时被拒绝。
- [ ] 同一幂等键只创建一个版本、审批实例和任务链；重复请求返回一致结果。
- [ ] 解析/OCR/字段抽取/规则/报告阶段分别记录状态，可从失败节点重试，超过阈值进入人工接管。
- [ ] 每条风险能定位附件、页码/位置、原文、字段、置信度、规则版本和分析时间；缺证据为人工确认。
- [ ] 规则引擎生成综合风险等级，LLM、Agent 无法直接改变风险结论或审批状态。
- [ ] 审批只允许当前审批人处理；通过、退回、驳回均写审批、状态和审计记录。
- [ ] 退回重提生成新版本，旧版本的风险、任务、意见和报告不被覆盖。
- [ ] 申请人、审批人、财务和管理员均无法越权读取或下载附件。
- [ ] OpenAPI、Pydantic schema 与前端 TypeScript 类型一致；错误码可由接口测试断言。

## 7. 【重点审核】

1. 【已确认】采用两阶段报告策略：分析阶段生成报告草稿，审批完成后固化最终报告。
2. 【已确认】证据待人工确认的单据可以进入审批，但审批人员必须逐条确认或处理后才能提交审批决定；最终决定仍由审批人员执行。
3. 【已确认】退回重提的新版本详情展示原版本审批意见，历史意见只读保留。
4. 【已确认】方法、文件路径和 API 按 `sentiment_anlyse` 的 `app/engines/front/test/var` 结构组织；实现前据此生成 `writing-plans`。
5. 【已确认】附件大小和页数均配置化；超限分别返回 `FILE_TOO_LARGE`、`PAGE_LIMIT_EXCEEDED`；附件必须病毒扫描通过后才能解析；幂等键有效期默认 24 小时；Celery 任务默认最多自动重试 3 次并采用指数退避，超过次数进入人工接管。

## 8. 单 Agent 方法级补充

| 方法/接口 | 文件 | 说明 |
|---|---|---|
| `process_review_message` | `app/services/review_session.py` | 读会话 → AgentEngine → Command 更新 → 写会话 |
| `plan_turn` | `engines/agent/turn_planner.py` | LLM 只输出 JSON `TurnPlan` |
| `validate_turn_plan` | `engines/agent/turn_validator.py` | Pydantic + 业务规则两层校验 |
| `clarify_turn` | `engines/agent/clarify.py` | 按 `ClarifyReason` 返回澄清问题 |
| `invoke_tool` | `engines/contracts/tool_registry.py` | 校验工具白名单、权限、超时和幂等键 |
| `stream_review_progress` | `app/routers/review_sessions.py` | SSE 输出 `progress`/`result` 事件 |

新增接口：

`POST /api/v1/review-sessions/{session_id}/messages/stream` 使用 SSE；普通消息接口仍返回 JSON。会话并发冲突返回 `SESSION_VERSION_CONFLICT`，工具调用失败返回结构化错误并保留 `agent_run_id`。
