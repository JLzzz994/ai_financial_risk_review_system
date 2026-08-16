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

### 2.1 当前选择：固定状态机，不采用动态 YAML/LangGraph 编排

本项目的审批流程是固定的顺序流程，MVP 不允许 Agent、YAML 或 LangGraph 动态改变审批节点。审批节点、顺序和状态转换由 Python 状态机与数据库中的审批流程对象共同约束：

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

如果未来需要支持复杂循环、并行或人工中断，应先新增版本化流程定义和审批配置，再单独评审是否引入 LangGraph；当前不预留动态流程执行器。

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
    intent: Literal["IDENTIFY_DOCUMENT", "START_ANALYSIS", "QUERY_RESULT", "CHITCHAT"]
    slots: dict[str, str]
    missing_slots: list[str]
    confidence: Decimal
```

- Prompt 强制 LLM 只输出合法 JSON，禁止 Markdown 代码块；
- 先用 Pydantic 校验结构，再用业务 Validator 校验意图、槽位、权限和状态；
- 失败时返回 `ClarifyReason`，由模板生成澄清问题；
- LLM 不直接修改 `slot_state_json`，只能生成 Command；
- 已确认的单据类型和单据编号不得重复询问。

提示词放在 `prompt/jinja2/`，通过 `prompt/loader.py` 加载，记录 `prompt_version`。

## 5. 工具注册与权限

每个工具必须声明：名称、输入 Schema、输出 Schema、权限、超时、重试、幂等策略和是否允许写入。

```python
class AgentTool(Protocol):
    name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    required_permission: str
    async def invoke(self, payload: BaseModel, context: ToolContext) -> BaseModel: ...
```

工具注册在 `engines/contracts/tool_registry.py`，Agent 只能调用注册表中的工具。审批状态变更不注册为 Agent 工具。

## 6. SSE 进度协议

多步骤分析使用 `StreamingResponse(..., media_type="text/event-stream")`：

```json
{"type":"progress","step":"ocr","status":"running","task_id":"uuid"}
{"type":"progress","step":"risk_analysis","status":"success","task_id":"uuid"}
{"type":"result","data":{"document_version_id":"uuid","report_status":"DRAFT"}}
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

## 10. 重点审核

- 是否确认审批流程和分析流水线均采用固定状态机，不引入动态 YAML/LangGraph 编排；
- 是否同意 SSE 只用于多步骤分析，普通查询使用普通 JSON；
- 是否同意 Agent 工具注册表禁止审批状态写入；
- 是否同意使用 `slot_state_json + state_version` 管理多轮会话；
- 是否同意提示词、模型和工具调用全部记录版本与审计链路。
