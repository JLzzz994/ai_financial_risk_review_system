#!/usr/bin/env bash
set -euo pipefail
docker_mode=0
seed=0
for arg in "$@"; do
  case "$arg" in
    --docker) docker_mode=1 ;;
    --seed) seed=1 ;;
    *) echo "用法: $0 [--docker] [--seed]" >&2; exit 2 ;;
  esac
done
project_root="$(cd "$(dirname "$0")/.." && pwd)"
if (( docker_mode )); then
  compose=(--env-file "$project_root/.env" -f "$project_root/docker-compose.yml" -f "$project_root/docker-compose.app.yml")
  docker compose "${compose[@]}" run --rm --no-deps api uv run alembic upgrade head
  if (( seed )); then docker compose "${compose[@]}" run --rm --no-deps api uv run python seed_demo_data.py; fi
else
  cd "$project_root"
  uv run alembic upgrade head
  if (( seed )); then uv run python seed_demo_data.py; fi
fi
