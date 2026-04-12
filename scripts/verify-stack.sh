#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${1:-http://127.0.0.1:8000}"
URI="${BASE_URL%/}/api/v1/health/ready"

if ! body=$(curl -fsS --max-time 30 "$URI"); then
  echo "Cannot reach $URI — start the API (e.g. uvicorn) and ensure Postgres, Redis, and Chroma are up." >&2
  exit 1
fi

CODE='
import json, sys
j = json.load(sys.stdin)
checks = j.get("checks") or {}
bad = [f"{k}: {v}" for k, v in checks.items() if v != "ok"]
if bad:
    print("Readiness degraded:", "; ".join(bad), file=sys.stderr)
    sys.exit(1)
print("OK: postgres, redis, chromadb —", j.get("status", ""))
'

if command -v python3 >/dev/null 2>&1; then
  echo "$body" | python3 -c "$CODE"
else
  echo "$body" | python -c "$CODE"
fi
