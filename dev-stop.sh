#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/Docker"
docker compose -f docker-compose.dev.yml down
