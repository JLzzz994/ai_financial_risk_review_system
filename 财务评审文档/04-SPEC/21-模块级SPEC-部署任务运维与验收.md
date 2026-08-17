# 部署、任务运维与系统验收模块——模块级 SPEC

> 状态：已生成，待用户审核

## 1. 部署拓扑与边界

```text
Vue build → FastAPI Router → Service/UoW → Repository → PostgreSQL
                                      ├→ Provider Adapter → httpx
                                      └→ ActionRegistry → 白名单工具
Redis → Celery Worker → OCR / LLM / RAG / Report
FileStorage → LocalFileStorage 或 MinIO Adapter
```

`Settings` 是配置唯一入口，生产和开发仅通过配置切换适配器。业务 Service 不直接依赖 MinIO、外部模型 SDK 或未注册工具。PostgreSQL 中的单据版本、风险、审批和报告是事实源；`document_version_id` 必须贯穿异步任务、证据和报告。审批状态只能由 `Approval Service / State Machine` 改变，Agent 不得改写。

## 2. 运行时配置与健康检查

- 必需配置缺失时启动失败，并输出脱敏字段名；
- `/health/live` 不访问外部依赖；`/health/ready` 检查 PostgreSQL、Redis、FileStorage 和 Provider 健康状态；
- Provider Adapter 统一使用 `httpx`，必须设置超时、关闭响应并释放连接；
- 生产禁止调试模式和公开对象存储 Bucket。

## 3. Celery 任务运维

任务记录任务 ID、`document_version_id`、阶段、状态、幂等键、重试次数、错误码、时间、Worker 和链路 ID。可重试错误默认指数退避，超过上限进入 `manual_review`；恢复从最后成功阶段继续，不重复写入解析、风险和报告。任务状态接口是前端事实来源，异常任务进入人工运维列表。

## 4. 验收矩阵

| 场景 | 验收要求 |
|---|---|
| 配置缺失 | 启动失败且不泄露密钥 |
| OpenAI-compatible 超时/非法 JSON | 超时按策略重试；非法 JSON 进入失败或人工接管，不写入伪造结果 |
| `httpx` 连接释放 | 正常、异常和取消路径均关闭响应并释放连接 |
| Provider 健康检查 | readiness 能识别不可用 Provider，返回 `503` |
| Action 权限拒绝 | 未授权或未注册 Action 返回拒绝并审计 |
| Session version conflict | 乐观锁冲突返回 `409`，不覆盖并发更新 |
| Celery 重试/幂等/人工接管 | 重试可恢复，重复投递不重复写事实，超限进入人工列表 |
| MinIO/本地切换 | 仅替换 Adapter 和配置，业务接口与对象键契约不变 |
| 审批禁止被 Agent 改写 | Agent 输出只能形成建议；状态变更必须经 Approval Service |

## 5. 验收标准

- [ ] Compose 可启动 API、PostgreSQL、Redis、Celery 和前端。
- [ ] LocalFileStorage 与 MinIO Adapter 契约测试通过。
- [ ] 健康检查正确区分存活、就绪和 Provider 不可用。
- [ ] 任务失败可重试、恢复、人工接管，幂等不重复。
- [ ] 费用报销单样板链路端到端通过。
- [ ] 权限、状态、版本、审计和报告接口符合已审核 SPEC。
