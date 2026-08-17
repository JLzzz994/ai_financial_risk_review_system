# 审核会话模块——方法级 SPEC

> 状态：已生成，待用户审核
> 重点：会话可见范围、轮次校验、澄清、乐观锁、幂等和 SSE 恢复。

## 1. 方法清单

| 方法 | 文件 | 职责 |
|---|---|---|
| `create_session` | `app/services/review_session_service.py` | 创建会话并初始化槽位 |
| `get_session` | `app/services/review_session_service.py` | 按数据权限读取会话 |
| `append_message` | `app/services/review_session_service.py` | 追加消息并推进一轮 |
| `plan_turn` | `engines/agent/turn_planner.py` | 识别意图、槽位和置信度 |
| `validate_turn_plan` | `engines/agent/turn_plan_validator.py` | 校验结构、权限和状态 |
| `build_clarification` | `engines/agent/clarify_responder.py` | 生成结构化澄清问题 |
| `start_analysis_command` | `app/services/review_session_service.py` | 通过确定性命令创建分析任务 |
| `stream_events` | `app/routers/review_sessions.py` | 推送 SSE 进度 |
| `close_session` | `app/services/review_session_service.py` | 关闭会话并保留历史 |

## 2. `append_message`

### 输入

```json
{"session_id":"uuid","content":"请分析这张费用报销单","client_message_id":"uuid","expected_state_version":3,"idempotency_key":"uuid"}
```

### 流程

1. 校验会话归属、状态和 `expected_state_version`；冲突返回 `SESSION_VERSION_CONFLICT`。
2. 以 `session_id + client_message_id` 或 `idempotency_key` 做幂等检查；重复请求返回首次结果。
3. 在同一 Unit of Work 中追加原始 `user` turn，读取槽位快照并调用 `plan_turn`。
4. 用 Pydantic 校验结构，再做意图、槽位、权限和状态校验；失败不覆盖正式槽位。
5. 按置信度处理：`>=0.75` 继续，`0.50-<0.75` 要求确认，`<0.50` 重新询问或转人工。
6. 缺槽位或需要确认时调用 `build_clarification`，澄清必须包含原因、缺失槽位、候选选项、最大轮次和预计解决时间，且不得重复询问已确认槽位。
7. 满足分析条件时只产生白名单 Command，由 Service/UoW 创建任务；Agent 不直接写分析或审批业务表。
8. 保存 `ReviewTurn`、消息元数据和新 `state_version` 后提交，返回助手消息、版本和任务引用。

消息历史使用游标分页，默认 `limit=50`、最大 `200`；`before` 和 `after` 不能同时使用。用户消息最大 10,000 字符，超限返回 `MESSAGE_TOO_LARGE`。附件原文由白名单 Action 按权限读取，不直接拼接到 Prompt。

## 3. `plan_turn` 与 `validate_turn_plan`

```python
class TurnPlan(BaseModel):
    intent: Literal["identify_document", "start_analysis", "query_result", "explain_finding", "chitchat"]
    slots: dict[str, str]
    missing_slots: list[str]
    confidence: Decimal
```

Validator 必须校验意图白名单、置信度 `0..1`、槽位适配当前单据类型、目标版本访问权限和会话当前状态。LLM 输出不能直接持久化，未注册 Action 或非法 Command 必须拒绝。

## 4. `start_analysis_command`

只有会话处于 `ready`/`running`、已确认 `document_id` 或 `document_version_id`、用户有分析权限、用户明确表达开始或点击确认，且同版本没有未完成相同任务时才允许创建。使用 `document_version_id + task_type + idempotency_key` 幂等。Command 只调用分析 Service。

## 5. `stream_events`

事件统一为：

```json
{"type":"progress","step":"ocr","status":"running","task_id":"uuid"}
{"type":"result","task_id":"uuid","document_version_id":"uuid","status":"succeeded"}
{"type":"error","task_id":"uuid","code":"TASK_FAILED"}
```

断线后按 `Last-Event-ID` 或任务状态接口恢复，只订阅已有任务；SSE 关闭不改变任务状态。

## 6. `close_session`

关闭后 `session_status=closed`，保留消息、槽位快照、turn 和任务引用；重复关闭幂等成功。已开始的分析任务不因关闭会话而取消；关闭后发送消息返回 `SESSION_CLOSED`。

## 7. 审批入口约束

Agent 不得生成或执行审批决定。所有审批决定只走 `POST /api/v1/approval-tasks/{task_id}/decision`，请求体为 `decision=approve|return|reject`；旧的 approve/return/reject 路径只能转发到同一 Service。

## 8. 测试用例

- 权限越界、会话关闭和消息超限被拒绝。
- 非法结构、非法意图、低置信度或缺槽位不创建任务。
- 澄清包含必需字段且不重复询问已确认槽位。
- 相同幂等键不重复追加 turn 或创建任务。
- 版本冲突不覆盖原消息和槽位；乱序消息不覆盖新状态。
- 非法 Action、审批 Action 和审批 Command 被拒绝。
- SSE 断线恢复不重复创建任务。
