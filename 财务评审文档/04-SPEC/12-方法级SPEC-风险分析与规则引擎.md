# 风险分析与规则引擎模块——方法级 SPEC

> 状态：已生成，待用户审核
>
> 【重点审核】分析任务幂等、规则执行顺序、风险等级汇总、证据不足、人工复核和 LLM 边界。

## 1. 方法清单

| 方法 | 文件 | 职责 |
|---|---|---|
| `create_analysis_task` | `app/services/risk_analysis_service.py` | 创建版本绑定的分析任务 |
| `run_analysis_stage` | `workers/risk_analysis_tasks.py` | 执行阶段任务和重试 |
| `evaluate_rules` | `engines/risk/rule_engine.py` | 执行确定性规则 |
| `validate_evidence` | `engines/risk/evidence_validator.py` | 检查证据完整性 |
| `aggregate_risk_level` | `engines/risk/risk_aggregator.py` | 计算综合等级 |
| `compare_amount` | `engines/risk/amount_comparator.py` | 市场价/历史金额比对 |
| `evaluate_supplier_risk` | `engines/risk/supplier_risk_evaluator.py` | 供应商风险查询和判定 |
| `update_review_status` | `app/services/manual_review_service.py` | 保存人工复核记录 |

## 2. `create_analysis_task`

1. 校验用户对 `document_version_id` 有分析权限；
2. 校验版本不可变且附件解析满足前置条件；
3. 以 `document_version_id + task_type + idempotency_key` 幂等；
4. 创建 `queued` 任务并记录请求人、规则版本和模型版本；
5. 投递 Celery 任务，返回 `task_id`。

## 3. `run_analysis_stage`

阶段执行顺序固定为：`OCR/抽取 → Evidence 校验 → 确定性规则 → 风险汇总 → LLM 解释/建议`。每阶段成功结果持久化后再进入下一阶段；可重试错误使用 Provider 契约中的统一超时、重试和幂等策略，超过上限将分析任务置为 `failed`，并将相关附件或风险项标记为 `manual_review`。任务不得重新解析已成功的前置结果。`manual_review` 不是 `analysis_tasks.task_status` 的值。

Provider 通过 `ProviderRegistry` 选择，Action 通过 `ActionRegistry` 选择；未注册、权限不足、外部调用未获脱敏授权或数据出域策略不满足时，调用失败并保留错误码，不得伪造成功。

## 4. `evaluate_rules`

规则输入只来自指定版本的结构化字段、解析结果、市场价、供应商档案和制度配置。输出 `RiskFindingDraft`：

```python
class RiskFindingDraft(BaseModel):
    finding_code: str
    finding_level: Literal["high", "medium", "low"]
    finding_message: str
    rule_version: str
    evidence: list[EvidenceRef]
    review_status: Literal["pending", "manual_review"]
```

同一 `document_version_id + finding_code + rule_version` 幂等；规则不能读取或改写其他版本结果。

一期规则注册表必须包含：`amount_invoice_consistency`、`line_total_consistency`、`batch_payment_consistency`、`market_price_reasonableness`、`consumption_anomaly`、`supplier_risk`、`duplicate_invoice`、`missing_attachment`。

## 5. `validate_evidence` 与 `aggregate_risk_level`

证据校验要求附件 ID、版本 ID、页码/坐标、原文片段、字段路径、置信度和解析版本齐全。缺任一关键字段时将风险项标记 `manual_review`。

汇总顺序：先排除 `dismissed` 和无证据项，再按已确认风险项取最高等级；无确认风险但存在待人工项时返回 `low` 或 `none`，并设置 `manual_review_required=true`。综合等级写入分析结果，不能由 LLM 覆盖。

## 6. `compare_amount`

金额比对只允许同币种。输出实际金额、参考下限/上限、差额、比例、数据来源、生效时间和规则版本；缺少参考数据时返回 `reference_unavailable`，不自行推断风险。

## 7. `evaluate_supplier_risk`

查询供应商名称、统一社会信用代码、收款账号、黑名单状态、风险标签、历史付款和异常记录。账号变化、黑名单或高风险标签形成可追溯风险项；查询结果记录来源和查询时间，不直接改变供应商主数据。

## 8. `update_review_status`

- 只有授权审核人员可以将 `pending`/`manual_review` 更新为 `confirmed` 或 `dismissed`；
- 必须填写处理意见，补充证据时绑定附件和位置；
- 每次操作写入 `manual_reviews` 和 `audit_logs`，不覆盖原始规则命中；
- AI、Agent 和申请人不能代替审核人员提交确认或排除。

## 9. Provider、Prompt 与错误处理契约

- `LlmAdapter` 只暴露 `async generate(request: LlmRequest) -> LlmResponse`；业务不得导入具体供应商 SDK。
- OpenAI-compatible Provider 配置至少包含 `base_url/api_key/model`，并支持 chat completion、JSON/schema、streaming、tool calling、timeout/retry、错误码映射和能力探测。
- 每次调用记录 Provider/model/model_version/prompt_version、输入范围、脱敏状态、`agent_run_id/task_id`、耗时、输出摘要和错误码。
- Prompt 统一位于 `engines/model/prompts/`，至少包括 `expense_field_completion`、`risk_explanation`、`review_suggestion`、`policy_qa`、`clarification`；模板渲染失败、非法 JSON 或业务校验失败转澄清/人工接管，不进入审批链路。
- 外部调用默认关闭；经授权时必须完成字段级脱敏、最小化传输和 `data_egress_policy` 校验。


- 分析任务重复创建、并发创建和失败重试。
- 规则版本固定，历史版本不可被新规则覆盖。
- 缺证据、低置信度和解析人工确认会阻止自动风险结论。
- 高/中/低/无风险等级汇总符合规则。
- 跨币种金额比对被拒绝或转人工，不做隐式汇率换算。
- 供应商黑名单、标签、历史异常和账号变化可追溯。
- 非授权用户不能查看或修改风险项；AI/Agent 不能写风险事实。
