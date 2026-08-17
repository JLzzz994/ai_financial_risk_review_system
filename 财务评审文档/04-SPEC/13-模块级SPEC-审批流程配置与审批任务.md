# 审批流程配置与审批任务模块——模块级 SPEC

> 状态：已生成，待用户审核
> 范围：审批流程模板配置、发布和版本化、顺序状态机执行、审批实例、审批任务、通过/退回/驳回和历史追溯。

## 1. 模块目标与边界

本模块负责管理员配置审批流程模板，并由固定顺序状态机为单据版本生成和推进审批任务。模板可配置、校验、发布和停用，但运行时执行器不允许 Agent、YAML 或 LangGraph 动态增删、跳过或重排节点。

包含按单据类型、金额区间、部门/组织和费用类别匹配模板；节点角色和范围配置；草稿、发布、停用和版本管理；审批实例、审批任务、决定和审计历史。不包含会签、或签、转交、加签、委托代理和 AI 自动审批。

## 2. 与 ActionRegistry 的边界

ActionRegistry 只提供财务辅助查询和解释能力：`query_document`、`query_document_version`、`list_attachments`、`retrieve_policy`、`retrieve_rule`、`explain_risk`、`create_clarification`。每个 Action 必须声明 `name/version`、输入/输出模型、权限、超时/重试/幂等策略、审计事件和写入范围。

`approve_document`、`return_document`、`reject_document`、`change_approval_node` 禁止注册。Agent、LLM 和 Action 均不能提交决定、修改审批状态或改变节点；审批任务只由本模块的确定性 Service/状态机推进。

## 3. 数据结构

复用 `approval_workflows`、`approval_workflow_nodes`、`approval_instances`、`approval_tasks`、`document_status_logs`、`audit_logs`。发布版本不可修改；实例创建时绑定 `workflow_id + workflow_version_no` 快照；任务只允许当前分配人处理一次。状态统一小写：模板 `draft/published/disabled`，实例 `pending/running/approved/returned/rejected/cancelled`，任务 `pending/approved/returned/rejected/cancelled`，决定 `approve/return/reject`。

## 4. 固定执行流程

```text
document_version
  → select published workflow
  → create approval_instance(pending)
  → analysis/manual review ready
  → create first approval_task(pending), instance running
  → current approver decision
      ├─ approve → next node task / final approved
      ├─ return → instance returned, document returned
      └─ reject → instance rejected, document rejected
```

执行器只按 `node_order` 顺序推进。模板停用只影响后续匹配，不影响已绑定实例。无匹配返回配置异常并告警，不自动放行。

## 5. 统一审批入口

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| `POST` | `/api/v1/approval-tasks/{task_id}/decision` | 当前审批人 | 提交 `approve`、`return` 或 `reject` |

请求体：

```json
{"decision":"approve","comment":"同意报销","expected_task_version":1}
```

旧的 `/approve`、`/return`、`/reject` 兼容路径只能转发到同一个 `ApprovalService.decide_task`，标记 deprecated，不得生成第二套状态机。

## 6. 退回重提与历史

退回关闭未完成任务并将实例和当前版本置为 `returned`；申请人编辑后创建新单据版本、新审批实例和新任务链，从首节点开始重新匹配提交时有效模板。旧实例、任务、意见和日志只读保留。

## 7. 验收标准

- 模板校验、发布、停用和版本绑定正确。
- 匹配冲突返回 `WORKFLOW_MATCH_CONFLICT`，无匹配返回 `WORKFLOW_NOT_FOUND`。
- 找不到唯一主审批人返回 `APPROVER_CONFIG_CONFLICT`，不跳过节点。
- 当前审批人只能处理本人 pending 任务一次。
- 版本冲突和重复幂等请求不重复推进节点。
- approve/return/reject 均写入状态和审计；Agent 不能调用审批决定。
- 退回重提创建新版本并从首节点开始，旧历史只读。
