# 审核会话模块——模块级 SPEC

> 状态：已生成，待用户审核
> 范围：审核会话、消息记录、槽位状态、多轮上下文、分析任务进度展示。

## 1. 模块目标与边界

会话为申请人和审核人员提供多轮交互入口，用于识别单据、补齐字段、发起分析、查询风险结果和解释报告。会话只保存交互上下文，不是单据、风险或审批事实来源。

包含：创建和查询会话；追加用户、助手和系统消息；保存已确认槽位、候选项、待询问项、进度和任务引用；通过 SSE 展示任务进度；并发控制、幂等、澄清和断线恢复。

不包含：直接修改单据字段、直接写入风险结论、直接改变审批状态、动态编排审批节点或替代正式业务接口。

## 2. ActionRegistry 边界

Agent 仅可调用以下财务辅助 Action：

```text
query_document
query_document_version
list_attachments
retrieve_policy
retrieve_rule
explain_risk
create_clarification
```

每个 Action 必须声明 `name/version`、`input_model/output_model`、`required_permission`、`timeout/retry/idempotency`、`audit_event` 和 `write_scope`。注册表统一执行权限、超时、重试、幂等和审计；默认 `write_scope=none`。

以下 Action 禁止注册：

```text
approve_document
return_document
reject_document
change_approval_node
```

Agent 不得直接修改单据、风险、审批实例或审批任务；审批决定只能通过统一审批 Service 处理。

## 3. 数据结构

复用 `review_sessions`、`review_turns` 和 `session_messages`：

| 对象 | 核心字段 | 约束 |
|---|---|---|
| `review_sessions` | `user_id`、`document_id`、`document_version_id`、`session_status`、`slot_state_json`、`state_version` | 会话归属用户；发起分析前绑定不可变版本；每次成功状态更新递增版本 |
| `review_turns` | `session_id`、`client_message_id`、`intent`、`slots`、`confidence`、`command_status` | 保存原始 turn、解析结果、命令状态和审计关联 |
| `session_messages` | `session_id`、`role`、`content`、`message_type`、`metadata_json` | 只追加，不覆盖历史；敏感内容按日志策略脱敏 |

`slot_state_json` 只保存 `confirmed`、`candidates`、`missing`、`pending_questions`、`progress` 和 `task_refs`。真实单据、`document_version`、风险结论、审批实例、审批任务及决定必须从版本化业务表查询。

状态统一小写：`collecting`、`ready`、`running`、`completed`、`failed`、`closed`。

## 4. 轮次数据流

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

缺少必要槽位或未确认意图时只生成澄清，不创建分析任务。LLM 输出不能直接写入数据库。

置信度固定为：`>=0.75` 继续；`0.50-<0.75` 要求确认；`<0.50` 重新询问或转人工。澄清必须包含原因、缺失槽位、候选选项、最大轮次和预计解决时间，不得重复询问已确认槽位。

## 5. 并发、幂等与重放

每轮请求携带 `session_id`、`expected_state_version`、`idempotency_key`。版本冲突返回 `SESSION_VERSION_CONFLICT`；重复幂等键返回原结果；消息顺序异常不得覆盖较新状态；审计记录保留原始 turn 和 command。

## 6. 接口范围

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/v1/review-sessions` | 创建会话 |
| `GET` | `/api/v1/review-sessions/{session_id}` | 查询会话 |
| `GET` | `/api/v1/review-sessions/{session_id}/messages` | 查询消息历史 |
| `POST` | `/api/v1/review-sessions/{session_id}/messages` | 发送消息 |
| `GET` | `/api/v1/review-sessions/{session_id}/events` | SSE 订阅 |
| `POST` | `/api/v1/review-sessions/{session_id}/close` | 关闭会话 |

关闭后只读保留历史，发送消息返回 `SESSION_CLOSED`。SSE 断线只恢复既有任务，不重复投递。
