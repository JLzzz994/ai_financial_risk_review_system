#!/usr/bin/env bash
set -euo pipefail

seed_demo=0
if [[ "${1:-}" == "--seed-demo" ]]; then seed_demo=1; fi
project_root="$(cd "$(dirname "$0")/.." && pwd)"
compose=(--env-file "$project_root/.env" -f "$project_root/docker-compose.yml" -f "$project_root/docker-compose.app.yml")

if [[ ! -f "$project_root/.env" ]]; then
  echo "缺少项目根目录 .env，请先复制 .env.example 并填写配置。" >&2
  exit 1
fi

docker compose "${compose[@]}" up -d postgres redis minio milvus-etcd milvus-minio milvus
docker compose "${compose[@]}" build api worker
if (( seed_demo )); then
  "$project_root/交付物/数据库初始化.sh" --docker --seed
else
  "$project_root/交付物/数据库初始化.sh" --docker
fi
docker compose "${compose[@]}" up -d api worker

cd "$project_root/front"
if [[ ! -d node_modules ]]; then npm ci; fi
exec npm run dev -- --host 127.0.0.1
