# 教育知识库 RAG 接入说明

当前审核系统只接入教育知识库项目的检索核心：外部 BGE-M3 稠密/稀疏向量服务、Milvus `kb_chunks` 混合检索和可选外部 BGE Reranker。外部项目的登录、Mongo 历史、聊天页面、WebSearch 和 LangGraph 问答服务不在当前 API 内复制。

运行边界：Milvus standalone（etcd + 专用 MinIO + Milvus）由本项目 Docker Compose 管理；BGE-M3 与 Reranker 的模型权重和推理进程由外部服务管理，不在本服务器部署，也不会进入镜像。

## 默认运行

`RAG_ENABLED=false` 是默认值。基础 API、Celery Worker 和现有风险规则不会连接知识库，也不会加载 BGE 模型。启用 RAG 的镜像只需额外安装 Milvus 客户端和 HTTP 客户端，不安装 `FlagEmbedding` 或 `torch`。

```powershell
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

关闭服务时停止 uvicorn/Celery 进程；Docker 部署使用：

```powershell
docker compose down
```

不需要删除 Milvus、PostgreSQL、Redis 或 MinIO 数据时，不要追加 `-v`。

## 启用 RAG

1. 启动本项目的 Milvus 及业务容器。开发机：

```powershell
docker compose -f docker-compose.yml -f docker-compose.app.yml up -d
```

服务器（隐藏 PostgreSQL/Redis/MinIO/Milvus 宿主机端口）：

```bash
export INSTALL_RAG_DEPS=true
docker compose -f docker-compose.yml -f docker-compose.app.yml -f docker-compose.server.yml build api worker
docker compose -f docker-compose.yml -f docker-compose.app.yml -f docker-compose.server.yml up -d
```

2. 先由 `S:\python_project\education_knowledeg_base` 的导入流程生成 Milvus `kb_chunks` 集合。导入端连接本项目 Milvus 时，开发机使用 `http://127.0.0.1:19530`；同一 Compose 网络内使用 `http://milvus:19530`。
3. 在 `.env` 中配置以下项目：

```dotenv
RAG_ENABLED=true
MILVUS_URI=http://milvus:19530
MILVUS_COLLECTION=kb_chunks
RAG_EMBEDDING_BASE_URL=https://embedding.example.internal/v1
RAG_EMBEDDING_API_KEY=<embedding-service-key>
RAG_EMBEDDING_TIMEOUT_SECONDS=60
RAG_RERANKER_ENABLED=false
# 启用重排时再填写
RAG_RERANKER_BASE_URL=https://reranker.example.internal/v1
RAG_RERANKER_API_KEY=<reranker-service-key>
RAG_RERANKER_TIMEOUT_SECONDS=60
```

4. 构建启用 RAG 依赖的 API/Worker 镜像。只安装 `requirements-rag.txt` 中的 `pymilvus` 和 `httpx`，不安装模型：

```bash
INSTALL_RAG_DEPS=true docker compose -f docker-compose.yml -f docker-compose.app.yml -f docker-compose.server.yml build api worker
```

5. 启动 API 后使用 Bearer Token 请求：

```http
POST /api/v1/rag/retrieve
Authorization: Bearer <access_token>
Content-Type: application/json

{"query":"差旅住宿费标准","top_k":5,"item_name":"财务制度"}
```

响应中的 `chunk_id`、`source_title`、`page_or_location`、`score` 和 `rule_version` 是制度依据；它们不等于上传附件的财务证据，不会改变风险或审批状态。

## 故障排查

- `rag_not_configured`：检查 `RAG_ENABLED`、`MILVUS_URI`、`MILVUS_COLLECTION` 和外部 Embedding URL。
- `rag_dependency_missing`：在当前 Python 环境安装 `requirements-rag.txt`。
- `rag_unavailable`：检查 Milvus、Embedding/Reranker 服务的网络、端口、API Key 和超时；集合至少应包含 `chunk_id`、`content`、`file_title`、`item_name`、`title`、`parent_title`、`part`、`dense_vector`、`sparse_vector`。
- `rag_query_failed`：检查查询是否为空、`top_k` 是否在 1 到 50 之间，以及外部服务是否返回符合契约的向量/分数。

## 外部模型服务契约

Embedding 服务：`POST {RAG_EMBEDDING_BASE_URL}/embed`，请求 `{"texts":["查询"]}`，响应至少包含 `dense` 二维数组和 `sparse` 稀疏对象数组，可选 `model_version`。

Reranker 服务：`POST {RAG_RERANKER_BASE_URL}/rerank`，请求 `{"query":"查询","documents":["候选片段"]}`，响应为 `{"scores":[...]}` 或 `{"results":[{"score":...}]}`，分数顺序必须与候选片段一致。

API 不返回第三方 SDK 堆栈、连接凭据、完整查询日志或完整证据原文到错误信息中。
