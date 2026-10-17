#!/usr/bin/env bash
# 停止 Bravo 的前后端进程（含陈旧进程与端口占用者）。
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT/.run"

kill_pidfile() {
  local file="$1"
  if [ -f "$file" ]; then
    local pid
    pid="$(cat "$file" 2>/dev/null || true)"
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
  fi
}

kill_pidfile "$RUN_DIR/frontend.pid"
kill_pidfile "$RUN_DIR/backend.pid"

# 端口占用者
for port in 3000 8000; do
  pids="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  [ -n "$pids" ] && kill $pids 2>/dev/null || true
done

# 陈旧进程（未监听端口但仍在运行、仍持有数据库的后端；以及残留的 next）
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
pkill -f "next-server" 2>/dev/null || true

# 等待优雅退出，超时则强制结束，避免陈旧事务长期占用 SQLite 写锁。
for _ in $(seq 1 20); do
  if ! pgrep -f "uvicorn app.main:app" >/dev/null 2>&1 \
     && [ -z "$(lsof -nP -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || true)" ]; then
    break
  fi
  sleep 0.5
done

# 强制清理残留
pkill -9 -f "uvicorn app.main:app" 2>/dev/null || true
for port in 3000 8000; do
  pids="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
done

echo "已停止 Bravo。"
