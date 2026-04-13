#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [[ ! -f "$ROOT/SRC/.env" ]]; then
  cp "$ROOT/SRC/.env.example" "$ROOT/SRC/.env"
  echo "Created SRC/.env from .env.example"
fi

cd "$ROOT/Docker"
if [[ ! -f env/.env.postgres ]]; then
  cp env/.env.postgres.example env/.env.postgres
fi
if [[ ! -f env/.env.grafana ]]; then
  cp env/.env.grafana.example env/.env.grafana
fi
if [[ ! -f env/.env.app ]]; then
  cp env/.env.app.example env/.env.app
fi

docker compose -f docker-compose.dev.yml up 

echo ""
echo "Dev infra is up (Postgres, Redis, Chroma, Prometheus, Grafana)."
echo "Next: cd SRC && uv sync --extra dev && uv run playwright install chromium && uv run alembic upgrade head && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo "Verify data plane: ./scripts/verify-stack.sh http://127.0.0.1:8000 (after API is running)"
echo "Ollama models: ollama pull gemma4:e2b && ollama pull qwen3-embedding:8b"
