#!/usr/bin/env bash
# 以「局域网可访问」方式启动 Bravo（手机/平板同 Wi-Fi 即可打开）。
# 前端通过同源 /api 代理访问后端，因此无需 CORS、也不依赖固定 IP。
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NODE_DIR="$HOME/.local/share/neoantigen/node/bin"
export PATH="$NODE_DIR:$PATH"

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 127.0.0.1)"

# 释放端口
for port in 3000 8000; do
  lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | xargs kill -9 2>/dev/null || true
done
sleep 1

echo "启动后端（0.0.0.0:8000）…"
(
  cd "$ROOT/backend"
  DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./neoantigen.db}" \
    nohup ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    > "$ROOT/.run/backend-lan.log" 2>&1 &
)

echo "启动前端（0.0.0.0:3000）…"
(
  cd "$ROOT/frontend"
  BACKEND_INTERNAL_URL="http://127.0.0.1:8000" \
    nohup node node_modules/.bin/next start -H 0.0.0.0 -p 3000 \
    > "$ROOT/.run/frontend-lan.log" 2>&1 &
)

for _ in $(seq 1 40); do
  curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1 && break
  sleep 1
done
for _ in $(seq 1 60); do
  curl -sf http://127.0.0.1:3000/ >/dev/null 2>&1 && break
  sleep 1
done

echo
echo "================================================"
echo "  手机/平板（同一 Wi-Fi）打开："
echo "      http://$LAN_IP:3000"
echo "  本机打开： http://localhost:3000"
echo "================================================"
