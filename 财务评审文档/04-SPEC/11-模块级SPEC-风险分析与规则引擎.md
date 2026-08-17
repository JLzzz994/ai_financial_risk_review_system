# 风险分析与规则引擎模块——模块级 SPEC

> 状态：已生成，待用户审核
>
> 范围：分析任务、确定性规则、风险项、证据引用、金额比对、供应商风险和人工复核入口。
>
> 【重点审核】规则引擎是否主导结论、风险等级规则、证据不足处理、LLM/Agent 边界和人工复核状态。

## 1. 模块目标与边界

本模块读取指定 `document_version_id` 的结构化字段、解析结果、附件证据和规则数据，生成可审计的风险项和综合风险等级，供人工复核与审批人员参考。

包含：

- 分析任务创建、状态查询、重试和恢复；
- 确定性风险规则执行和规则版本记录；
- 金额与市场价/历史数据比对；
- 供应商黑名单、信用和异常记录查询；
- 风险项证据绑定和人工复核状态更新；
- LLM 字段补全、解释和建议；Agent 只编排白名单工具。

不包含：审批决定、审批节点流转、报告正式固化和会计记账。

## 2. 数据结构

复用 `analysis_tasks`、`risk_findings`、`manual_reviews`、`market_price_references`、`supplier_profiles`、`attachment_parse_results`：

| 对象 | 关键字段 | 约束 |
|---|---|---|
| 分析任务 | `document_version_id`、`stage`、`task_status`、`retry_count`、`rule_version` | 绑定不可变版本，阶段可恢复 |
| 风险项 | `finding_level`、`finding_code`、`finding_message`、`review_status`、`evidence_json` | 规则命中可复现；证据不足不得自动汇总 |
| 人工复核 | `risk_finding_id`、`reviewer_id`、`review_status`、`comment` | 只追加记录，不能删除原始命中 |
| 市场价 | 品类、规格、价格区间、币种、生效期、来源 | 规则执行时记录引用版本 |
| 供应商档案 | 供应商、风险标签、黑名单、历史异常 | 查询结果记录来源和时间 |

状态使用小写：

- 分析任务：`queued`、`querying_document`、`loading_attachments`、`parsing_attachments`、`analyzing`、`succeeded`、`failed`、`cancelled`；
- 风险等级：`high`、`medium`、`low`、`none`；
- 复核状态：`pending`、`confirmed`、`dismissed`、`manual_review`。

## 3. 风险判定原则

1. 确定性规则引擎是风险命中的唯一事实来源，执行顺序固定为：`OCR/抽取 → Evidence 校验 → 确定性规则 → 风险汇总 → LLM 解释/建议`。
2. 每个风险项必须绑定规则编码、规则版本、分析时间和证据。
3. 证据至少包含附件、页码/坐标、原文片段、字段路径和置信度。
4. 缺失证据或置信度不足时，风险项为 `manual_review`，不自动参与综合等级；无证据只能返回 `manual_review`。
5. LLM 只能补全字段、解释规则命中或提出建议，不能新增已生效风险命中、决定最终风险等级、修改 evidence、改变审批状态或创建/跳过审批节点。
6. Agent 只能编排 `ActionRegistry` 中的白名单 Action，不得直接写入风险表；风险事实由确定性 Service/Processor 提交。
7. 外部 OCR/LLM/RAG 调用默认关闭，或必须经过字段级脱敏授权和 `data_egress_policy` 校验。

### 3.1 Provider 与 Prompt 依赖

OCR、LLM、Embedding、RAG Provider 必须由 `ProviderRegistry` 管理，每个 Provider 记录 `name/version/capabilities/input_model/output_model/required_permission/timeout_policy/retry_policy/idempotency_policy/health_check/data_egress_policy`。LLM 业务接口只依赖 `LlmAdapter.generate(LlmRequest) -> LlmResponse`，不得直接依赖供应商 SDK。

Prompt 模板统一位于 `engines/model/prompts/`，至少包括 `expense_field_completion`、`risk_explanation`、`review_suggestion`、`policy_qa`、`clarification`。调用必须记录 Provider、模型、模型版本、Prompt 版本、输入范围、脱敏状态、`agent_run_id/task_id`、耗时、输出摘要和错误码；渲染/非法 JSON/业务校验失败只能澄清或人工接管。

## 4. 分析流程

```text
queued
  → querying_document
  → loading_attachments
  → parsing_attachments
  → analyzing
  → succeeded
```

异常时进入 `failed`，可从失败阶段恢复；用户取消进入 `cancelled`。阶段结果和任务日志均绑定 `document_version_id`，不覆盖历史分析。

### 4.1 一期必实现规则

1. 单据与发票金额一致性；
2. 明细与总金额一致性；
3. 批量付款一致性；
4. 市场价格合理性；
5. 消费行为异常；
6. 供应商风险；
7. 重复票据风险；
8. 附件缺失风险。

## 5. 综合风险等级

默认规则建议：

- 存在任一已确认 `high` 风险项 → 综合等级 `high`；
- 不存在 `high`，存在任一已确认 `medium` → `medium`；
- 仅存在 `low` 或无风险 → `low` 或 `none`；
- `pending`、`dismissed`、证据不足的 `manual_review` 不直接提升自动综合等级，但必须在报告和审批页面展示；
- 综合等级只由规则引擎计算，人工复核只能确认或排除具体风险项，不能直接改写规则命中。

阈值和数量修正通过版本化规则配置管理。

## 6. 核心代码文件

```text
app/
├── routers/analysis_tasks.py
├── routers/risk_findings.py
├── routers/amount_comparisons.py
├── routers/supplier_risks.py
├── services/risk_analysis_service.py
└── services/manual_review_service.py
engines/
├── risk/rule_engine.py
├── risk/rule_registry.py
├── risk/risk_aggregator.py
├── risk/evidence_validator.py
├── risk/amount_comparator.py
├── risk/supplier_risk_evaluator.py
├── adapters/llm.py
└── agent/tools/risk_tools.py
workers/
└── risk_analysis_tasks.py
test/
├── engines/risk/test_rule_engine.py
├── engines/risk/test_risk_aggregator.py
└── app/risk/test_risk_router.py
```

## 7. 接口范围

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| `POST` | `/api/v1/analysis-tasks` | 数据范围 | 创建指定版本分析任务 |
| `POST` | `/api/v1/documents/{document_id}/analysis` | 数据范围 | 项目说明兼容入口，转发到分析任务 Service |
| `GET` | `/api/v1/analysis-tasks/{task_id}` | 数据范围 | 查询任务状态和当前步骤 |
| `GET` | `/api/v1/analysis-tasks/{task_id}/findings` | 数据范围 | 任务视角查询风险项投影 |
| `POST` | `/api/v1/analysis-tasks/{task_id}/retry` | 数据范围 | 重试失败任务 |
| `GET` | `/api/v1/documents/{document_id}/risk-findings` | 数据范围 | 查询风险项和证据 |
| `PATCH` | `/api/v1/risk-findings/{finding_id}/review-status` | 授权审核人员 | 更新人工复核状态 |
| `GET` | `/api/v1/amount-comparisons` | 财务/审批/授权范围 | 查询金额比对结果 |
| `GET` | `/api/v1/documents/{document_id}/amount-comparison` | 财务/审批/授权范围 | 项目说明兼容入口 |
| `GET` | `/api/v1/supplier-risks/{supplier_id}` | 财务/审批/授权范围 | 查询供应商风险 |
| `GET` | `/api/v1/suppliers/{supplier_code}/risks` | 财务/审批/授权范围 | 项目说明兼容入口 |

## 8. 验收标准

- [ ] 分析任务按阶段执行，可重试、恢复、取消并保留错误。
- [ ] 规则命中可追溯到规则版本和证据。
- [ ] 一期 8 类必实现规则均可执行并有测试样本。
- [ ] 金额比对支持同币种、市场价和历史数据引用。
- [ ] 供应商风险展示黑名单、标签、历史异常和账号变化。
- [ ] 风险项支持 `pending`、`confirmed`、`dismissed`、`manual_review`。
- [ ] 证据不足或无证据只能 `manual_review`，不得自动参与风险汇总。
- [ ] LLM/Agent 不能直接改变风险事实、综合等级、evidence 或审批状态。
- [ ] Provider 均经 `ProviderRegistry` 选择，Prompt 版本和脱敏状态写入审计。
- [ ] 非法 JSON、模板渲染失败、Provider 超时/错误均可映射为稳定错误，并不得进入审批链路。
- [ ] 所有查询执行版本绑定和数据权限校验。

## 9. 【重点审核】

1. 综合风险等级规则和 `manual_review` 是否参与汇总。
2. 金额比对的参考数据和阈值来源。
3. 供应商风险的字段和数据来源。
4. 人工复核是否可以确认、排除或补充证据。
