# 慧经营对账异常智能审核：生产架构说明

## 1. 目标

把“订单、账单、退款、调账、回款”统一成一个版本化审核对象，并保证：

- 确定性业务规则可复现。
- 每个风险项可追溯到原始业务证据。
- RAG 只提供制度依据。
- LLM 只生成解释和处理建议。
- AI 不直接修改审批状态。
- 异步任务失败可恢复、可人工接管。

## 2. 总体架构

```text
                    ┌──────────────────┐
                    │ ERP / 平台账单   │
                    │ 退款 / 调账 /回款│
                    └────────┬─────────┘
                             │
                             v
                    ┌──────────────────┐
                    │ FastAPI          │
                    │ 上传 / 创建审核  │
                    └────────┬─────────┘
                             │
                ┌────────────┴────────────┐
                v                         v
       ┌──────────────────┐      ┌──────────────────┐
       │ PostgreSQL       │      │ MinIO            │
       │ 版本化业务数据   │      │ 原始账单/凭证    │
       └────────┬─────────┘      └────────┬─────────┘
                │                         │
                └────────────┬────────────┘
                             v
                    ┌──────────────────┐
                    │ Celery Worker    │
                    └────────┬─────────┘
                             │
           ┌─────────────────┼─────────────────┐
           v                 v                 v
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ OCR/Parser   │  │ Rule Engine  │  │ Redis/SSE    │
    │ 证据结构化   │  │ 风险事实     │  │ 进度/恢复    │
    └──────┬───────┘  └──────┬───────┘  └──────────────┘
           │                 │
           └────────┬────────┘
                    v
             ┌──────────────┐
             │ RiskFinding  │
             │ PostgreSQL   │
             └──────┬───────┘
                    │
                    v
        ┌──────────────────────────┐
        │ BGE-M3 → Milvus          │
        │ → BGE-Reranker           │
        └────────────┬─────────────┘
                     v
             ┌──────────────┐
             │ RagEvidence  │
             └──────┬───────┘
                    v
             ┌──────────────┐
             │ LLM Explain  │
             │ 解释 + 建议  │
             └──────┬───────┘
                    v
          ┌────────────────────┐
          │ 人工复核 / 审批     │
          │ ReviewReport       │
          └────────────────────┘
```

## 3. 两类证据

### Evidence：业务事实证据

来源于账单、凭证或结构化业务记录，包含：

- attachment_id
- page_or_location
- original_text
- field_name
- confidence
- rule_version

用途：证明“这笔业务实际上发生了什么”。

### RagEvidence：制度依据

来源于平台结算规则、财务制度、内部 SOP，包含：

- chunk_id
- content
- source_title
- score
- rule_version
- page_or_location

用途：证明“按照什么制度处理”。

这两类证据禁止混用。

## 4. Worker 边界

`ReconciliationWorker` 的生产顺序：

```text
load_context
  ↓
evaluate_reconciliation_rules
  ↓
SqlRiskRepository.append_findings
  ↓
ReconciliationExplanationService.prepare
  ↓
ExplanationAdapter.explain
  ↓
ReconciliationReportService.render
```

### 为什么 ExplanationAdapter 单独拆接口

原系统的 `LlmAdapter.extract()` 负责 OCR 后的字段抽取。如果复用同一个宽接口做风险解释，会把：

- 字段抽取
- 风险解释

两个职责混在一起。

因此新增窄接口 `ExplanationAdapter.explain()`，输入中携带已经确定的：

- rule_code
- risk_level
- finding_status
- 受约束 prompt

模型没有修改规则状态的接口能力。

## 5. 事务边界

建议生产接入时由 Celery Task 持有一个任务级数据库会话：

1. 查询和装配对账上下文。
2. 追加风险事实并 flush。
3. 外部 RAG/LLM 调用不持有数据库写锁。
4. 模型结果返回后重新进入短事务保存解释/报告。

避免在长时间模型调用期间持有数据库事务。

## 6. 失败策略

- OCR/Parser 失败：自动重试，超过 3 次人工接管。
- 关键字段低置信度：规则状态转 `manual_review`。
- RAG 不可用：不改变规则事实，报告标记“制度依据待人工核对”。
- LLM 不可用：保留规则结果，解释部分为空，不伪造成功解释。
- SSE 断线：客户端通过 `last_event_id` 重放 Redis 历史事件。

## 7. 面试回答模板

如果被问“这个项目里大模型到底负责什么”，可以回答：

> 我们没有让大模型直接判断财务异常。订单金额、平台结算、退款、调账和回款这些确定性问题先由规则引擎形成 RiskFinding，并绑定原始证据；之后用 BGE-M3 + Milvus + Reranker 检索平台规则和财务制度，大模型只基于风险事实和检索证据生成解释与处理建议。这样既保留模型的自然语言能力，又不会让模型覆盖确定性财务结论。
