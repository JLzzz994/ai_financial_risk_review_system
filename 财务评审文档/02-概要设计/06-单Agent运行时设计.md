# 单 Agent 运行时设计

> 状态：已补充，待审核  
> 适用范围：智能审核对话、费用报销单分析、OCR/规则/RAG/LLM 工具编排。  
> 设计原则：单 Agent 编排，多专业引擎协作；Agent 不直接修改审批状态。

## 1. 运行时架构

```text
POST /api/v1/review-sessions/{session_id}/messages
        ↓
FastAPI Router
        ↓
ReviewSessionService
  1. 读取会话状态
  2. AgentEngine 处理一轮消息
  3. 确定性 Command 更新状态
  4. 保存会话和消息
        ↓
AgentEngine
  ├── TurnPlanner：识别意图和槽位，只输出 JSON
  ├── TurnPlanValidator：校验结构、权限和业务范围
  ├── ClarifyResponder：失败时生成澄清问题
  ├── ToolRouter：按白名单调用工具
  └── ProgressWriter：输出 SSE 进度
        ↓
Tool Registry
  ├── query_document
  ├── parse_attachment
  ├── run_risk_rules
  ├── retrieve_policy
  ├── explain_finding
  └── get_review_report
```

Agent 只能返回命令或工具调用结果，不能直接写入 `approval_tasks`、`approval_instances` 或单据最终状态。

## 2. 流程编排选型

### 2.1 当前选择：固定顺序执行器 + 可配置、可发布的流程模板

本项目的审批执行器固定为顺序状态机，但审批模板不是写死的。管理员可以在流程配置模块中按单据类型、金额区间、组织和角色维护模板，经过校验和发布后供新实例绑定。已创建的审批实例绑定发布时的模板版本，模板后续修改不会改变进行中的实例。

MVP 不允许 Agent、YAML 或 LangGraph 在运行时动态改变审批节点。审批节点、顺序和状态转换由 Python 顺序状态机执行，并由数据库中的已发布模板约束：

```text
草稿
  → 已提交
  → 解析/OCR/规则分析
  → 风险复核
  → 审批节点 1
  → 审批节点 2（如配置存在）
  → 已通过 / 已退回 / 已驳回
```

分析流水线同样按固定阶段执行：上传 → 解析 → OCR → 字段抽取 → 规则分析 → 报告草稿。Agent 只负责在分析阶段调用白名单工具，不能创建、删除、跳过或重排审批节点。

如果未来需要支持会签、或签、循环或并行，应先扩展版本化模板和确定性执行器，再单独评审是否引入 LangGraph；当前不实现动态流程执行器。

## 3. 会话状态与轮次事务

`review_sessions.slot_state_json` 保存已确认槽位、候选项、待询问项和当前流程节点；`session_messages.metadata_json` 保存意图、槽位变更、任务 ID 和进度引用。

每轮消息遵循：

1. 以 `session_id + state_version` 获取会话并加乐观锁。
2. 将输入写入 `pending_turn`，不立即覆盖正式状态。
3. Agent 输出 `TurnPlan`，经 Validator 校验。
4. 由确定性 Command 修改槽位和流程状态。
5. 事务内写入消息、状态和任务引用；成功后提交，失败回滚 `pending_turn`。

并发更新返回 `SESSION_VERSION_CONFLICT`，前端重新拉取会话后由用户重试。

## 4. LLM 路由、校验与澄清

```python
class TurnPlan(BaseModel):
    intent: Literal["identify_document", "start_analysis", "query_result", "chitchat"]
    slots: dict[str, str]
    missing_slots: list[str]
    confidence: Decimal
```

- Prompt 强制 LLM 只输出合法 JSON，禁止 Markdown 代码块；
- 先用 Pydantic 校验结构，再用业务 Validator 校验意图、槽位、权限和状态；
- 失败时返回 `ClarifyReason`，由模板生成澄清问题；
- LLM 不直接修改 `slot_state_json`，只能生成 Command；
- 已确认的单据类型和单据编号不得重复询问。

Prompt 统一放在 `engines/model/prompts/`，模板至少包括 `expense_field_completion`、`risk_explanation`、`review_suggestion`、`policy_qa`、`clarification`；每个模板具有不可变 `prompt_version`。每次 Provider 调用记录 `provider/model/model_version/prompt_version`、`input_scope/redaction_status`、`agent_run_id/task_id`、`latency/output_summary/error_code`。渲染、结构化解析或业务校验失败时只能澄清或人工接管，不得提交成功结果。

## 5. 工具注册与权限

工具调用统一经过 `ActionRegistry`（兼容既有 Tool Registry 术语）。每个 Action 必须声明：名称、输入 Schema、输出 Schema、权限、超时、重试、幂等策略、数据出域策略和是否允许写入。

```python
class AgentAction(Protocol):
    name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    required_permission: str
    async def invoke(self, payload: BaseModel, context: ToolContext) -> BaseModel: ...
```

Action 注册、权限检查、超时/重试和幂等键由 `ActionRegistry` 统一执行；Agent 只能调用注册表中的白名单 Action。审批状态变更、风险事实写入和证据修改不注册为 Agent Action；Agent 只能返回 Command，由确定性 Service/Processor 提交。

## 6. SSE 进度协议

多步骤分析使用 `StreamingResponse(..., media_type="text/event-stream")`：

```json
{"type":"progress","step":"ocr","status":"running","task_id":"uuid"}
{"type":"progress","step":"risk_analysis","status":"success","task_id":"uuid"}
{"type":"result","data":{"document_version_id":"uuid","report_status":"draft"}}
```

每帧以 `\n\n` 结尾，JSON 使用 `ensure_ascii=False`。前端按 `type` 分发；断线后通过任务状态接口恢复，不重复创建分析任务。

## 7. 提示词与模型调用

```text
prompt/
├── jinja2/expense_field_completion.jinja2
├── jinja2/risk_explanation.jinja2
├── jinja2/review_suggestion.jinja2
└── loader.py
```

真实财务数据默认只进入私有化模型；外部模型调用必须通过脱敏策略检查。每次调用记录模型、模型版本、提示词版本、输入范围、输出摘要、耗时、错误和 `agent_run_id`。

## 8. 结构化日志与链路追踪

```text
RequestIdMiddleware
  → request_id / ContextVar
  → agent_run_id
  → task_id
  → tool_call_id
  → audit_logs
```

日志不得记录完整身份证号、银行卡号、发票原文和附件内容。API、Agent、Celery 和工具调用必须能通过 `request_id`、`agent_run_id` 和 `task_id` 关联。

## 9. 生命周期与依赖注入

- 数据库引擎、Redis、HTTP 客户端和模型客户端采用 `init_xxx()`/`dispose_xxx()`，在 FastAPI lifespan 初始化和释放；
- Session 每请求创建，不缓存；无状态工具注册表和编译后的流程可缓存；
- 路由通过 `Annotated[..., Depends(...)]` 注入服务；Agent Engine 依赖由 builder 统一组装。

## 11. 任务 4 补充：ActionRegistry 契约与可调用边界

`ActionRegistry` 是 Agent 可调用的业务动作注册中心，不是审批执行器，也不是通用 Python 函数入口。注册表在应用启动时完成静态注册；运行时只能从已注册白名单中选择 Action，不支持通过用户输入、动态 YAML、`eval` 或模型输出新增、替换、删除 Action。

每个 Action 必须声明以下契约字段：

```text
name
version
input_model
output_model
required_permission
timeout_policy
retry_policy
idempotency_policy
audit_event
write_scope
```

其中 `input_model`/`output_model` 必须可由 Pydantic 校验；`required_permission` 在调用前检查；超时、重试和幂等策略由注册表统一执行；`audit_event` 记录调用主体、目标版本、输入摘要、结果摘要和错误码；`write_scope` 明确允许写入的业务范围。默认 `write_scope=none`，不得扩大到审批状态、风险事实或证据原文。

MVP 允许的财务辅助 Action 仅包括：

```text
query_document
query_document_version
list_attachments
retrieve_policy
retrieve_rule
explain_risk
create_clarification
```

以下名称禁止注册为 Agent Action：

```text
approve_document
return_document
reject_document
change_approval_node
```

`parse_attachment`、`run_risk_rules`、`get_review_report` 等分析能力如需提供，必须通过分析任务或内部 Service 的确定性入口实现；本任务不将其扩展为新增 Agent Action。Agent 只能返回白名单 Action 结果或白名单 Command，业务状态变更由 `Service/UoW` 在事务内完成。

## 12. 会话轮次、澄清与审批边界统一说明

审核会话的统一数据流为：

```text
message
  → TurnPlanner
  → Pydantic 结构校验
  → 置信度判断
  → SlotState 更新
  → 白名单 Command
  → Service/UoW
  → ReviewTurn 保存
  → ReviewSession.state_version 更新
```

`ReviewSession` 只保存交互上下文：已确认槽位、候选项、待询问项、当前进度、任务引用和消息元数据；真实单据、`document_version`、风险结论、审批实例、审批任务及审批决定必须从版本化业务表查询。会话状态不得覆盖业务事实，也不得作为审批状态机的第二事实源。

置信度阈值固定为：`confidence >= 0.75` 继续下一步；`0.50 <= confidence < 0.75` 要求用户确认；`confidence < 0.50` 重新询问或转人工。澄清结果必须包含原因、缺失槽位、候选选项、最大轮次和预计解决时间；已确认槽位不得重复询问。Agent 不得自行修改阈值、跳过确认或直接启动审批决定。

每轮请求必须携带 `session_id`、`expected_state_version` 和 `idempotency_key`。版本冲突统一返回 `SESSION_VERSION_CONFLICT`；相同幂等键返回首次结果；乱序消息不得覆盖较新的会话状态。审计记录保留原始 turn 和生成的 command，便于重放与追溯。

审批决定唯一入口为 `POST /api/v1/approval-tasks/{task_id}/decision`，请求体使用 `decision=approve|return|reject`。兼容旧路径只能转发到同一个审批 Service，不得创建第二套状态机。

## 13. 重点审核

- 是否确认审批执行器固定为顺序状态机，同时允许管理员配置并发布版本化审批模板；
- 是否确认 Agent 不能在运行时增删、跳过或重排审批节点；
- 是否同意 SSE 只用于多步骤分析，普通查询使用普通 JSON；
- 是否同意 Agent 工具注册表禁止审批状态写入；
- 是否同意使用 `slot_state_json + state_version` 管理多轮会话；
- 是否同意提示词、模型和工具调用全部记录版本与审计链路。
