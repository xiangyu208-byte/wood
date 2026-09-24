#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "未找到 Docker，请先安装并启动 Docker。" >&2
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "已由 .env.example 创建 .env，请在正式部署前修改数据库密码。"
fi

if [ "${1:-}" = "--gpu" ]; then
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
else
  docker compose -f docker-compose.yml up -d --build
fi

FRONTEND_PORT=$(sed -n 's/^FRONTEND_PORT=//p' .env | head -n 1)
echo "系统启动完成：http://localhost:${FRONTEND_PORT:-8088}"
