# AGENTS.md

## 项目概述

本项目是“财务单据智能风险审核系统”，目标是用 AI 辅助财务单据解析、风险识别、人工复核、顺序审批和报告生成。

当前仓库以设计文档、页面原型和项目级技能为主，尚未提交后端或前端业务代码。任何实现任务都必须先以文档中的已确认决策为准，不要根据目录草图直接假设代码已经存在。

## 已确认架构与技术栈

- Python 3.12+
- FastAPI + Pydantic
- SQLAlchemy + Alembic
- PostgreSQL
- Redis + Celery；长耗时任务与 API 进程分离
- Vue 3 + TypeScript
- OpenAPI 作为前后端接口契约
- OCR、LLM、RAG 通过独立适配器接入
- 文件访问统一通过 `FileStorage` 抽象；本地开发使用本地存储，生产使用 MinIO
- 模块化单体优先，不拆成微服务
- 单 Agent 编排、多专业引擎协作；Agent 只能调用白名单工具，不能直接改变审批状态
- 审批流程和分析流水线采用固定状态机，不使用 Agent、YAML 或 LangGraph 动态改变审批节点

## 业务边界

- R-01：先完整打通费用报销单，其他 4 类单据复用通用框架。
- R-02：最终通过、退回、驳回由审批人员决定，AI 只提供辅助结果。
- R-03：申请人只能看本人单据；审批人员只能看分配任务；财务人员按授权组织范围查看；管理员主要维护配置，不默认查看全部业务数据。
- R-04：退回重提创建新版本，从第一个审批节点重新开始；旧任务、意见和结果保留历史。
- R-05：MVP 只支持顺序多节点审批，不实现会签、或签、加签、转审和委托。
- R-06：金额使用 Python `Decimal` 和 PostgreSQL `NUMERIC(18,2)`；MVP 只支持单币种，禁止隐式汇率换算。
- R-07/R-09：确定性规则引擎负责风险判断；LLM 只做补全、解释和建议；Agent 只编排工具；RAG 只检索制度和规则依据。
- R-08：每条风险必须绑定附件、页码/位置、原文片段、字段、置信度、规则版本和分析时间；证据不足时进入人工确认。
- R-10/R-17：真实财务数据优先使用私有化 OCR/模型；外部调用必须经过脱敏、授权、加密、留存和审计控制。
- R-11：上传、解析、OCR、分析、报告阶段必须记录状态、重试、错误、幂等键和人工接管。
- R-12：每次提交/重新提交生成不可变 `document_version`；附件、解析、风险、审批和报告绑定同一 `document_version_id`。

## 当前目录结构

```text
.
├── AGENTS.md
├── 财务评审文档/
│   ├── 财务风险评审项目说明.md
│   ├── 01-PRD/
│   ├── 02-概要设计/
│   ├── 03-页面原型/
│   └── 04-SPEC/
├── skills/
│   ├── python-*/       # 通用 Python 技能
│   └── financial-*/    # 当前财务项目技能
└── .git/
```

当前页面原型包含 6 个统一风格页面，文件位于 `财务评审文档/03-页面原型/`。

## 目标代码结构

实现代码参考 `S:\python_project\workspace\sentiment_anlyse`：

```text
app/
├── routers/       # FastAPI 路由、鉴权和响应编排
├── schemas/       # Pydantic 请求/响应模型
├── services/      # 用例编排和事务边界
└── exceptions/    # 业务异常和错误码
engines/
├── common/        # 共享仓储、存储和基础能力
├── contracts/     # 工具、领域契约和输入/输出模型
├── expense_reimbursement/
├── ocr/           # OCR 适配器
├── model/         # LLM/RAG 适配器
├── report_engine/
└── tasks/         # Celery 任务
front/src/
├── views/
├── api/
├── types/
└── components/
test/
var/
├── uploads/       # 本地 FileStorage，不能提交真实财务文件
└── logs/
```

当前这些代码目录尚未创建；新增代码时保持 `app → engines → infrastructure` 的单向依赖。

## 文档与技能使用顺序

1. `financial-data-object-skill`：表、字段、Python/PostgreSQL 类型、约束和生命周期。
2. `financial-spec-skill`：模块级或方法级 SPEC，精确到文件、方法、接口和验收。
3. `diagram-builder` / `excalidraw-diagram`：架构图、流程图、状态机、ER 图；生成后必须渲染检查。
4. `writing-plans`：SPEC 审核通过后拆解实现计划。

优先使用 `skills/financial-*`，需要通用方法时参考 `skills/python-*`。

## 开发规范

### Python、API 和数据库

- 文件、模块、函数和变量使用 `snake_case`；类和模型使用 `PascalCase`。
- 路由只做校验、鉴权、数据范围检查和响应转换；业务规则放在 service/domain，数据库访问放在 repository。
- 金额禁止使用 `float`；统一使用 `Decimal`。
- API schema 与 SQLAlchemy 模型分离；不要把 ORM 对象直接作为 API 响应。
- 数据库 Session 不缓存；依赖使用 FastAPI `Depends` 或 builder 组装。
- 外部 OCR、LLM、RAG、MinIO 调用必须经过适配器，设置超时、重试、错误映射和审计。

### Agent、LLM 和 Celery

- Agent 只能调用注册表中的白名单工具，不得调用审批状态变更工具。
- LLM 输出必须经过 Pydantic 和业务规则两层校验；失败返回澄清问题或模板化结果。
- Prompt 使用外部 Jinja2 模板并记录 `prompt_version`，禁止在 Python 中内联长提示词。
- Celery 任务只传递稳定 ID 和幂等键，不传文件二进制或 ORM 实例。
- 上传、解析、OCR、字段抽取、规则分析、报告分别记录阶段状态。
- 默认最多自动重试 3 次并采用指数退避，超过上限进入人工接管；具体配置可由环境变量覆盖。

### 数据、安全和文档

- 数据对象、字段和 25 张既有表必须与 `05-数据对象文档.md` 一致，除非用户明确批准变更。
- 数据库只保存对象存储元数据，不保存本地绝对路径。
- 日志不得输出完整身份证号、银行卡号、发票原文、附件内容或模型敏感输入。
- 状态变更、人工复核、审批决定、外部模型调用和敏感下载写入审计日志。
- 文件使用 UTF-8；交付前扫描 `浼`、`寰`、`鎵`、`鏄`、`锛`、`銆`、`�` 等乱码。

## 常用命令

当前仓库尚未有 `pyproject.toml`、前端 `package.json` 或可执行测试代码，以下为实现后命令。

实现阶段统一使用 `uv` 管理 Python 依赖和命令：先执行 `uv sync`，再使用 `uv run ...`；不要混用裸 `pip` 或系统 Python。

### Git 和文档检查

```powershell
git status --short
git branch -vv
git log --oneline -5
rg -n "待确认|重点审核|TODO|xxx" 财务评审文档 skills
rg -n "Java|Spring|MyBatis|MySQL" 财务评审文档/04-SPEC skills/financial-*
```

### Python 后端

```powershell
uv sync
uv run ruff check .
uv run mypy app engines
uv run pytest -q
uv run python -c "from app.main import app; print(app.title)"
```

### 数据库迁移

```powershell
uv run alembic check
uv run alembic upgrade head
uv run alembic downgrade -1
```

未确认迁移内容前，不要对生产数据库执行 `upgrade` 或 `downgrade`。

### 前端

```powershell
Set-Location front
npm ci
npm run lint
npm run type-check
npm run build
```

### Docker Compose

```powershell
docker compose config
docker compose up -d postgres redis minio
docker compose logs -f api worker
```

仅在存在并审核过 compose 文件后执行，不要把真实财务文件上传到本地 MinIO。

## 测试方法

### 单元测试

覆盖金额精度、单币种约束、必需附件、单据编号、版本不可变性、状态转换、风险规则、证据绑定和权限范围。

### API 测试

覆盖草稿、提交、附件上传、风险复核、审批决定、退回重提和报告查询；验证 OpenAPI、错误码、`request_id`、`Idempotency-Key` 和越权响应。

### 异步任务测试

模拟 OCR、LLM、RAG、FileStorage 超时或异常，验证阶段状态、重试、幂等、人工接管、SSE `progress/result` 事件和断线恢复。

### 前端测试

验证 14 个页面的统一布局、空/错/加载状态、权限隐藏、分页、证据展开、审批确认和刷新后状态恢复。

### RAG 黄金问题集评估

- 评估集使用 UTF-8 CSV，包含问题、参考答案和脱敏样本/证据绑定字段。
- 评估程序必须产出生成答案、上下文证据、正确性、忠实度、上下文相关性、上下文召回率和上下文精确率；最终结果文档固定为四要素加五大指标共 9 列。
- 评估依赖显式 `llm` 和 `embedding` 工具适配器；运行结果、工具版本和脱敏输入输出截取写入 `var/logs/evaluation/`。
- 每次 RAG、规则或提示词改动都必须执行：跑评估 → 分析分数和 bad case → 查日志定位 → 改进 → 回归评估。

## 提交流程

```powershell
git status --short
git add <明确文件路径>
git commit -m "docs(范围): 简要说明"
git push origin main
```

不要提交 `.env`、密钥、真实附件、`var/uploads` 业务文件、日志或构建产物。推送前确认 `git diff --cached` 和目标分支；外部推送必须获得用户明确授权。

### Git 忽略规则

- `.gitignore` 采用“默认忽略、代码白名单”策略。
- 允许提交的实现目录为 `app/`、`engines/`、`front/`、`test/`、`tests/` 和 `alembic/`；必要的 Python、前端、Docker 和数据库配置文件可提交。
- 文档、原型图、技能文件、`.learnings/`、`var/`、日志、上传文件和构建产物默认不纳入新提交。
- `.gitignore` 只影响未跟踪文件；停止跟踪已有文档前必须先确认范围，再使用 `git rm --cached`，不得删除工作区文件。

## 当前注意事项

1. 当前仓库仍处于文档先行阶段，不能声称后端、前端、Celery 或 Docker 已实现。
2. `06-单Agent运行时设计.md` 已补充运行时设计，但 SSE、Prompt、工具注册和会话并发策略仍需审核。
3. 固定审批流程不能由 Agent、YAML 或 LangGraph 动态改写；新增审批节点必须走版本化配置和评审。
4. 生产对象存储使用 MinIO，但业务代码只能依赖 `FileStorage`，不能直接调用 MinIO SDK。
5. 任何风险结论都必须有证据；没有证据只能是“待人工确认”。
6. 新增表、字段、状态、接口、外部模型或权限时，先更新数据对象文档/SPEC并逐条审核，再写代码。

## 自我改进记录

遇到命令失败、用户纠正、架构修正、知识缺口或可复用的更好做法时，按 `self-improving-agent` 规范记录到 `.learnings/`：

- `.learnings/LEARNINGS.md`：纠正、洞察、知识缺口和最佳实践；
- `.learnings/ERRORS.md`：命令、工具和外部服务错误；
- `.learnings/FEATURE_REQUESTS.md`：暂未实现的用户能力需求。

记录不得包含密钥、Token、密码、完整财务数据或其他敏感信息。可复用且已验证的规则再提升到本文件。
