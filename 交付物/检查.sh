#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
compose=(--env-file "$project_root/.env" -f "$project_root/docker-compose.yml" -f "$project_root/docker-compose.app.yml")
curl -fsS http://127.0.0.1:8000/health/live
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsSI http://127.0.0.1:5173/ | head -n 1
docker compose "${compose[@]}" ps
