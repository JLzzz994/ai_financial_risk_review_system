# 审批流程配置与审批任务模块——方法级 SPEC

> 状态：已生成，待用户审核
> 重点：模板发布校验、匹配优先级、任务分配、审批决定事务和退回重提。

## 1. 方法清单

| 方法 | 文件 | 职责 |
|---|---|---|
| `create_workflow_draft` | `app/services/workflow_config_service.py` | 创建模板草稿 |
| `validate_workflow` | `app/services/workflow_config_service.py` | 校验条件、节点和角色 |
| `publish_workflow` | `app/services/workflow_config_service.py` | 发布不可变版本 |
| `match_workflow` | `engines/approval/workflow_matcher.py` | 匹配已发布模板 |
| `create_approval_instance` | `app/services/approval_service.py` | 创建实例和首任务 |
| `resolve_assignee` | `engines/approval/assignee_resolver.py` | 解析唯一主审批人 |
| `decide_task` | `app/services/approval_service.py` | 处理 approve/return/reject |
| `resubmit_returned_version` | `app/services/approval_service.py` | 新版本重新建立审批链 |

## 2. `validate_workflow`

校验单据类型有效；金额下限不大于上限；同一适用范围无重叠；至少一个节点；`node_order` 从 1 连续递增；角色 active；节点范围合法；`approval_mode=sequential`；不得把 Agent 或系统任务配置为最终审批人。失败返回可审计的配置错误，不发布。

## 3. `publish_workflow`

事务内锁定同条件已发布模板，校验后创建递增 `version_no`，写发布审计。发布版本及节点、匹配条件不可修改；修改必须创建新草稿。停用仅影响后续匹配，已绑定实例继续使用原版本。

## 4. `match_workflow`

输入 `document_type`、总金额、申请部门/组织和费用类别。优先级为：费用类别更具体 > 部门/组织 > 金额区间 > 单据类型默认模板。同优先级多个匹配返回 `WORKFLOW_MATCH_CONFLICT`，禁止随机选择；无匹配返回 `WORKFLOW_NOT_FOUND`，提交不得自动放行。

## 5. `create_approval_instance` 与 `resolve_assignee`

提交时先创建绑定 `workflow_id` 和 `workflow_version_no` 的 `pending` 实例；分析和人工复核完成后置为 `running` 并按首节点创建 pending 任务。按 `approver_role` 和 `approver_scope_json` 查找有效用户；节点必须配置唯一 `primary_approver_id`，且该用户属于有效候选集合。无法解析唯一主审批人返回 `APPROVER_CONFIG_CONFLICT`，不能跳过节点或创建会签任务。

## 6. `decide_task`

1. 校验 Token、功能权限、当前任务分配人、任务状态 pending、证据人工复核完成。
2. 使用请求 `idempotency_key` 和任务行锁保证一次处理；重复键返回原结果。
3. `approve` 完成当前任务；存在下一节点则创建下一任务，最终节点将实例和单据置为 approved。
4. `return` 保存意见，关闭未完成任务，将实例和单据置为 returned。
5. `reject` 保存意见，将实例和单据置为 rejected，终止当前版本审批。
6. 在同一事务写审批状态、状态日志和审计日志；提交后发送通知。

唯一接口为 `POST /api/v1/approval-tasks/{task_id}/decision`，请求体：

```json
{"decision":"approve","comment":"同意报销","expected_task_version":1,"idempotency_key":"uuid"}
```

旧的 approve/return/reject 路径只转发到本方法，不得实现独立状态转换。

## 7. `resubmit_returned_version`

申请人编辑退回或撤回草稿并提交时，创建新单据版本、新审批实例和新任务链；按提交时有效模板从首节点开始。旧实例、任务、意见和操作日志只读保留，新版本不复用旧任务状态。

## 8. 测试用例

- 节点顺序、条件重叠、无效角色、非顺序模式和最终 Agent 审批人被拒绝。
- 发布后模板不可修改，历史实例继续使用旧版本。
- 匹配优先级、冲突和无匹配处理正确。
- 找不到唯一审批人不跳过节点。
- 非当前审批人、已处理任务、证据未确认和版本冲突不能提交决定。
- 相同幂等键不重复推进节点或创建任务。
- approve/return/reject 状态转换、审计和通知事务边界正确。
- 退回重提从新版本首节点开始，旧历史只读。
- Agent ActionRegistry 无法调用任何审批 Action。
