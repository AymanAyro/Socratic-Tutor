Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$srcEnv = Join-Path $here "SRC\.env"
$srcEnvExample = Join-Path $here "SRC\.env.example"
if (-not (Test-Path $srcEnv)) {
  Copy-Item $srcEnvExample $srcEnv
  Write-Host "Created SRC\.env from .env.example"
}

Set-Location (Join-Path $here "Docker")
if (-not (Test-Path "env/.env.postgres")) {
  Copy-Item "env/.env.postgres.example" "env/.env.postgres"
}
if (-not (Test-Path "env/.env.grafana")) {
  Copy-Item "env/.env.grafana.example" "env/.env.grafana"
}
if (-not (Test-Path "env/.env.app")) {
  Copy-Item "env/.env.app.example" "env/.env.app"
}

docker compose -f docker-compose.dev.yml up -d

Write-Host ""
Write-Host "Dev infra is up (Postgres, Redis, Chroma, Prometheus, Grafana)."
Write-Host "Next: cd SRC; uv sync --extra dev; uv run alembic upgrade head; uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000"
Write-Host "Verify data plane: .\scripts\verify-stack.ps1 -BaseUrl http://127.0.0.1:8000 (after API is running)"
Write-Host "Ollama models: ollama pull phi3:mini; ollama pull qwen2.5:7b; ollama pull nomic-embed-text"
