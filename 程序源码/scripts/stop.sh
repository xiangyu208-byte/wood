#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

if [ "${1:-}" = "--gpu" ]; then
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml down
else
  docker compose -f docker-compose.yml down
fi
