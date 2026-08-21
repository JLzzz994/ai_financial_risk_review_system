# 财务单据智能风险审核系统｜可运行交付包

本目录是当前仓库的可运行交付入口，覆盖前端、FastAPI 后端、PostgreSQL 迁移、Redis/Celery、MinIO 文件存储、脱敏示例数据、接口契约和一条完整审核演示链路。

RAG 默认关闭。启用时，本项目 Compose 运行 Milvus standalone（etcd、专用 MinIO、Milvus）；BGE-M3 与 BGE-Reranker 通过 `.env` 中的外部 HTTP 地址调用，服务器不部署模型权重。启用镜像构建参数 `INSTALL_RAG_DEPS=true` 只安装 `requirements-rag.txt` 中的客户端依赖。

## 快速启动

前置条件：Docker Engine + Compose v2、Python 3.11、uv、Node.js 20+、npm。

在项目根目录执行：

```powershell
Copy-Item .env.example .env
# 按需修改 .env 中的密钥和端口
.\交付物\启动.ps1 -SeedDemo
```

Linux/macOS：

```bash
cp .env.example .env
chmod +x 交付物/*.sh
./交付物/启动.sh --seed-demo
```

启动后访问：

- 前端：`http://127.0.0.1:5173/`
- API 文档：`http://127.0.0.1:8000/docs`
- 存活检查：`http://127.0.0.1:8000/health/live`
- 就绪检查：`http://127.0.0.1:8000/health/ready`

不需要示例数据时，去掉 `-SeedDemo` 或 `--seed-demo`。示例数据脚本是幂等的，只写入固定的脱敏演示记录。

## 登录账号

执行带 `-SeedDemo` 的启动命令后，可使用以下账号登录，密码均为 `Demo123!`：

| 用户名 | 角色 | 演示重点 |
| --- | --- | --- |
| `demo_applicant` | 申请人 | 创建/提交报销单、查看报告 |
| `demo_approver` | 审批人 | 风险复核、第一审批节点 |
| `demo_finance` | 财务人员 | 第二审批节点、报告和规则 |

前端 README 中的 `li.qian` 等账号只属于 mock 模式，不会写入 PostgreSQL。

## 关闭与检查

```powershell
.\交付物\检查.ps1
.\交付物\关闭.ps1
```

```bash
./交付物/检查.sh
./交付物/关闭.sh
```

关闭脚本只停止容器和前端进程，不删除数据卷。需要清空数据库时必须先备份并明确执行 `docker compose down -v`。

## 交付目录

```text
交付物/
├── 后端/                 # 后端源码快照、迁移和依赖清单
├── 前端/                 # Vue 源码、锁文件和 dist 构建产物
├── 数据库/               # 迁移、初始化和种子数据说明
├── 文件存储/             # FileStorage 契约、示例和适配器说明
├── 示例数据/             # 演示账号和固定脱敏数据摘要
├── 接口/                 # OpenAPI JSON 契约
├── 接口说明.md
├── 完整审核演示链路.md
├── 验收清单.md
├── 启动.ps1 / 启动.sh
├── 关闭.ps1 / 关闭.sh
├── 检查.ps1 / 检查.sh
└── 数据库初始化.ps1 / 数据库初始化.sh
```

## 生产注意事项

- `.env`、JWT 密钥、数据库密码和真实附件不得进入交付包或 Git。
- 示例数据只用于开发/验收环境，生产环境不要执行种子脚本。
- PostgreSQL 是业务事实源；Redis 只用于队列、锁和短期状态。
- 附件业务只依赖 `FileStorage`，本地开发使用 `LocalFileStorage`，生产使用 MinIO 适配器。
- 审批状态只能由统一 decision 服务推进，AI 结果不能直接改变审批状态。
