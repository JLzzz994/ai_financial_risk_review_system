# 慧策·慧经营对账异常智能审核演示链路

本演示用于说明一条异常订单如何从业务数据进入规则、RAG、AI 解释和人工复核链路。

## 演示 Case

订单 `ERP-20260901-0001`：

- ERP 应收：1280.00 元
- 平台结算：1180.00 元
- 退款：0 元
- 调账：0 元
- 同订单结算记录数：2
- 已到回款日，但未匹配到实际回款
- 账单关键字段解析置信度：0.97

因此至少会形成三类重点风险事实：

1. 平台结算金额比 ERP 净应收少 100 元。
2. 同订单存在 2 条结算记录，需要排查重复结算或合法拆分。
3. 已到回款日但没有实际回款，需要核对银行流水和账期。

## 端到端链路

```text
ERP订单 + 平台账单 + 退款 + 调账 + 回款
                   ↓
      PaddleOCR / Excel Parser / API
                   ↓
      ParsedReconciliationRow
                   ↓
        ReconciliationContext
                   ↓
         确定性规则引擎
                   ↓
 RiskFinding + 原始附件位置 + 置信度
                   ↓
   BGE-M3 -> Milvus 混合召回 -> Reranker
                   ↓
        平台规则 / 财务制度证据
                   ↓
       LLM 解释和处理建议
                   ↓
        人工复核 / 财务审批
                   ↓
          版本化审核报告
```

## 为什么规则在 LLM 前面

金额差异、重复结算、退款金额、回款缺失属于可以通过结构化数据确定的事实，不应该
交给大模型自由判断。LLM 的职责是把风险事实结合制度依据解释成财务人员能快速理解
的结论和处理建议。

因此代码中风险引擎不调用 LLM；AI 解释服务也明确禁止修改规则等级、规则状态、金额
差异和审批状态。

## OCR / Excel 解析怎么讲

PDF、扫描图片通过 PaddleOCR/PP-OCRv4 解析；平台 Excel 账单走结构化 Excel Parser。
不同输入最终归一化到同一个 `ParsedReconciliationRow` 契约。

关键字段包括：订单号、结算单号、结算金额、退款金额、调整金额、结算主体和回款主体。
解析结果必须保留来源附件、页码/单元格位置和字段置信度。关键字段置信度过低时不进入
自动确认，而是转人工复核。

## RAG 怎么讲

检索 Query 不是直接拿用户自然语言，而是由规则事实构造，例如：

```text
tmall + reconciliation.settlement_amount_difference
+ 对账规则 + 结算规则 + 财务处理制度 + 人工复核要求
```

生产环境对应：BGE-M3 Embedding -> Milvus -> BGE-Reranker。检索返回的
`RagEvidence` 与业务附件 `Evidence` 分开保存：前者证明“制度怎么规定”，后者证明
“这笔订单实际发生了什么”。

## Celery 怎么讲

完整异步任务按以下阶段推进：

```text
PARSING
 -> NORMALIZING
 -> RULE_EVALUATING
 -> POLICY_RETRIEVING
 -> EXPLAINING
 -> AGGREGATING
```

任务使用幂等键避免重复提交，失败自动重试最多三次，仍失败时进入人工接管。当前仓库
保留真实 Worker 接入边界；未配置 Celery/模型服务时不会伪造成功。

## 一键离线演示

```bash
python examples/run_reconciliation_demo.py
```

该脚本使用：

- `examples/reconciliation_case.json`
- `examples/policy_evidence.json`

展示规则和报告链路。它不会冒充在线 PaddleOCR、Milvus、Reranker 或 LLM 调用。

## 面试中 90 秒讲法

这个项目是慧经营多平台电商对账异常审核。我把 ERP 订单、平台结算、退款、调账和实际
回款统一绑定到一个不可变审核版本。账单 PDF/图片通过 PaddleOCR，Excel 账单直接做
结构化解析，同时保留字段原始位置和置信度。金额差异、重复结算、退款和回款异常这些
确定性问题先由规则引擎判断，避免让 LLM 参与财务事实计算。规则命中后，再通过
BGE-M3、Milvus 和 BGE-Reranker 检索平台结算规则及内部财务制度，让 LLM 基于风险事实
和制度证据生成解释及处理建议。低置信度、证据不足或者异步任务连续失败三次都会转人工
复核，AI 不允许覆盖规则结果，也不能直接改变审批状态。最终风险、原始凭证位置、制度
依据和人工审核全部绑定到同一个版本化报告，保证全过程可追溯。
