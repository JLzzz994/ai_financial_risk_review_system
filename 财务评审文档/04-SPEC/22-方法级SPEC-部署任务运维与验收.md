# 部署、任务运维与系统验收模块——方法级 SPEC

## 1. 方法清单

| 方法 | 职责 |
|---|---|
| `check_liveness` | 不访问依赖，返回进程存活状态 |
| `check_readiness` | 检查 PostgreSQL、Redis、FileStorage 和 Provider |
| `record_task_event` | 记录任务状态、版本、幂等键和指标 |
| `retry_failed_task` | 按错误类型和重试策略恢复任务 |
| `backup_database` / `restore_database` | 备份数据库并执行恢复演练 |
| `run_expense_chain` | 执行费用报销端到端验收 |

## 2. 方法行为

`check_liveness` 进程可响应即返回 `200`；`check_readiness` 任一必要依赖不可用返回 `503`，不得泄露连接字符串和密钥。Provider 健康检查使用统一 Adapter，不在路由中直接创建客户端。

`record_task_event` 必须携带 `document_version_id`、阶段、状态、幂等键、重试次数和链路 ID。`retry_failed_task` 仅对可重试错误执行指数退避；超过上限进入人工接管。恢复从最后成功阶段继续，重复调用不得重复写解析结果、风险项或报告。

所有 OpenAI-compatible 调用经 Provider Adapter 使用 `httpx`，覆盖超时、非法 JSON、连接释放和取消清理。Action 先经 `ActionRegistry` 白名单与权限校验；Agent 不能直接改变审批状态。

## 3. 端到端验收

1. 登录并创建费用报销单草稿；
2. 上传附件并切换 LocalFileStorage / MinIO；
3. 提交不可变版本，运行 OCR、LLM、RAG 和 Report Celery 任务；
4. 校验规则风险项、证据和人工复核；
5. 仅由审批人员通过 Approval Service 提交 `approve`、`return` 或 `reject`；
6. 校验最终报告与 `document_version_id` 一致并可审计；
7. 模拟配置缺失、Provider 超时、非法 JSON、重复投递、版本冲突、越权和审批改写，确认错误码、重试和人工接管符合矩阵。

## 4. 发布门禁

- 单元测试覆盖配置、状态机、规则、权限、金额、版本和 Adapter 契约；
- 集成测试覆盖 PostgreSQL、Redis、Celery、FileStorage、Provider 和 `httpx` 连接释放；
- 端到端样板链路成功率为 100%；
- 幂等重复请求不得产生重复版本、任务、审批实例或报告；
- 权限越权请求 100% 拒绝并审计；
- 备份恢复演练验证版本、附件、风险、审批、报告和审计关联完整；
- 未通过任何关键门禁不得进入生产。
