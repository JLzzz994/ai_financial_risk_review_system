#!/usr/bin/env bash
set -euo pipefail

service_name="${1:-}"
app_dir="${APP_DIR:-/opt/financial-review/financial-review}"

cd "$app_dir"
set -a
. /root/risk/.env
set +a

# risk 项目的基础设施运行在 Docker 中；宿主机进程使用映射到本机的端口。
export DOCUMENT_BACKEND=postgres
export AUTH_BACKEND=postgres
export DATABASE_URL="$(printf '%s' "$DATABASE_URL" | sed 's#@postgres:5432#@127.0.0.1:5432#')"
export REDIS_URL="$(printf '%s' "$REDIS_URL" | sed 's#redis://redis:6379#redis://127.0.0.1:6379#g')"
export CELERY_BROKER_URL="$(printf '%s' "$CELERY_BROKER_URL" | sed 's#redis://redis:6379#redis://127.0.0.1:6379#g')"
export CELERY_RESULT_BACKEND="$(printf '%s' "$CELERY_RESULT_BACKEND" | sed 's#redis://redis:6379#redis://127.0.0.1:6379#g')"
export MINIO_ENDPOINT="$(printf '%s' "$MINIO_ENDPOINT" | sed 's#^minio:9000#127.0.0.1:9000#')"
export EMBEDDING_BASE_URL=http://127.0.0.1:8081/v1
export MINIO_SECURE=false
export FRONTEND_DIST_DIR="${FRONTEND_DIST_DIR:-/opt/financial-review/frontend-dist}"
export PYTHONUNBUFFERED=1

case "$service_name" in
  api)
    exec "$app_dir/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000
    ;;
  worker)
    exec "$app_dir/.venv/bin/celery" -A app.tasks.celery_app worker --loglevel=INFO
    ;;
  *)
    echo "usage: $0 {api|worker}" >&2
    exit 2
    ;;
esac
