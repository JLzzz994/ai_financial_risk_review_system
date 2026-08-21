# 后端交付说明

后端快照包含 `app/`、`engines/`、`alembic/`、`alembic.ini`、`pyproject.toml`、`uv.lock`、`requirements.txt` 和 `seed_demo_data.py`。

## 本地运行

在项目根目录：

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

另一个终端启动异步 Worker：

```bash
uv run celery -A app.tasks.celery_app worker --loglevel=INFO
```

## 分层边界

```text
Router -> Service/Unit of Work -> Repository/Adapter
```

OCR、LLM、RAG 和文件存储都通过适配器接入；API 不直接拼接 SQL；长任务由 Celery Worker 执行；金额使用 `Decimal` 和 PostgreSQL `NUMERIC(18,2)`。

RAG 默认关闭。需要启用教育知识库检索时，先准备 Milvus `kb_chunks` 集合和外部 BGE-M3/Reranker HTTP 服务；本服务器只运行 Compose 中的 Milvus 及其依赖，不安装模型权重。启用镜像构建参数 `INSTALL_RAG_DEPS=true` 后会安装 `requirements-rag.txt` 中的 Milvus/HTTP 客户端，并参考项目根目录的 `docs/rag-integration.md`（交付快照见 `../说明/RAG接入说明.md`）。
