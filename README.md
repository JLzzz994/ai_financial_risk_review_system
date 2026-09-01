# 慧策·慧经营对账异常智能审核系统

面向多平台电商对账场景，对 ERP 订单、平台结算账单、退款、金额调整和实际回款进行自动核验；通过账单解析、确定性规则、RAG 制度检索和大模型解释生成可追溯的风险结论与处理建议，并保留人工复核和审批。

> 本分支由通用财务风险审核系统适配而来。核心原则：**规则负责判断，AI 负责解释；证据不足则转人工。**

## 核心业务链路

```text
ERP订单 / 平台账单 / 退款 / 调账 / 回款
                    ↓
         文件上传与版本绑定
                    ↓
     PaddleOCR / Excel Parser
                    ↓
       结构化字段 + 证据位置
                    ↓
          确定性规则引擎
                    ↓
       RiskFinding 风险事实
                    ↓
 BGE-M3 → Milvus → BGE-Reranker
                    ↓
      平台规则 / 财务制度证据
                    ↓
          LLM 解释 + 建议
                    ↓
       人工复核 / 审批 / 报告
```

## 为什么不是让 LLM 直接判断风险

金额差异、重复结算、退款金额、回款缺失等属于确定性业务规则。如果让 LLM 直接判断，会产生口径漂移和不可复现问题。因此系统把职责拆成三层：

1. **业务事实层**：ERP、平台账单、退款、回款、OCR 证据。
2. **确定性判断层**：规则引擎输出风险等级、命中状态、差异金额。
3. **AI 解释层**：RAG 检索制度依据，LLM 只能解释既有风险事实并给出建议。

## 已实现的对账规则

- 订单应收与平台结算金额差异
- 退款异常
- 重复结算
- 实际回款缺失/金额不一致
- 金额调整异常
- 结算主体与回款主体不一致
- OCR/解析关键字段质量异常

## 关键数据模型

```text
financial_documents
    ↓
document_versions
    ↓
reconciliation_cases
    ├── reconciliation_orders
    ├── reconciliation_settlements
    ├── reconciliation_refunds
    ├── reconciliation_adjustments
    └── reconciliation_remittances

附件证据：
document_attachments
    ↓
attachment_parse_results

分析产物：
analysis_tasks
    ↓
risk_findings
    ↓
manual_reviews / approval_*
    ↓
review_reports
```

所有分析产物都绑定不可变 `document_version_id`，历史版本不覆盖。

## 生产分析阶段

```text
queued
  ↓
parsing
  ↓
normalizing
  ↓
rule_evaluating
  ↓
policy_retrieving
  ↓
explaining
  ↓
aggregating
  ↓
succeeded
```

失败任务有界重试，超过上限进入人工接管，不伪造成功状态。

## 目录重点

- `engines/risk/reconciliation_engine.py`：对账确定性规则。
- `app/models/reconciliation.py`：对账领域表。
- `app/repositories/sql_reconciliation_repository.py`：对账数据装配与持久化。
- `app/services/reconciliation_explanation_service.py`：RAG 制度证据和受约束 Prompt。
- `engines/model/explanation_contracts.py`：风险解释模型窄接口。
- `app/tasks/reconciliation_worker.py`：生产对账分析编排。
- `app/services/reconciliation_report_service.py`：审核报告生成。
- `examples/run_reconciliation_demo.py`：可控 Demo。
- `docs/reconciliation-demo-walkthrough.md`：面试演示讲解。

## Demo

```bash
python examples/run_reconciliation_demo.py
```

Demo 使用：

- `examples/reconciliation_case.json`：异常订单案例。
- `examples/policy_evidence.json`：模拟 RAG 检索结果。

Demo fixture 不冒充真实线上 OCR、Milvus 或模型服务。

## 生产依赖

- FastAPI
- PostgreSQL / SQLAlchemy / Alembic
- Redis / Celery
- MinIO
- PaddleOCR / PP-OCRv4
- BGE-M3
- Milvus
- BGE-Reranker
- OpenAI-compatible LLM / vLLM
- SSE

外部模型能力通过 Adapter/Provider 边界接入，业务层不直接依赖厂商 SDK。

## 面试时最值得讲的 5 个设计点

1. **规则与 LLM 分层**：LLM 不参与确定性金额判断。
2. **事实证据与制度证据分离**：`Evidence` 和 `RagEvidence` 分别回答“发生了什么”和“制度怎么规定”。
3. **版本化审核对象**：风险、报告、审批都绑定 `document_version_id`。
4. **低置信度人工接管**：OCR 关键字段置信度不足不能自动形成结论。
5. **异步可恢复执行**：Celery + Redis + SSE，支持幂等、重试、状态恢复和进度追踪。

详细架构见 `docs/reconciliation-production-architecture.md`。
