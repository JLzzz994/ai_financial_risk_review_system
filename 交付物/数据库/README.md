# 数据库初始化说明

数据库结构由 Alembic 迁移维护，不手工执行散落的 `CREATE TABLE`。初始化入口是上级目录的 `数据库初始化.ps1` 或 `数据库初始化.sh`。

## 本地 Python 环境

```bash
uv run alembic upgrade head
uv run python seed_demo_data.py       # 可选，仅开发/验收环境
```

## Docker Compose 环境

```bash
./交付物/数据库初始化.sh --docker
./交付物/数据库初始化.sh --docker --seed
```

迁移会创建单据、不可变版本、附件、分析任务、风险发现、审批工作流/任务、报告、审计日志等表。种子脚本使用固定 UUID 和冲突忽略写入，可重复执行；生产环境不要执行它。
