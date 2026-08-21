#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
compose=(--env-file "$project_root/.env" -f "$project_root/docker-compose.yml" -f "$project_root/docker-compose.app.yml")
if [[ -f "$project_root/.env" ]]; then
  docker compose "${compose[@]}" stop api worker postgres redis minio milvus milvus-etcd milvus-minio
fi
