#!/usr/bin/env bash
# 启动 Bravo（后端 + 前端）并打开浏览器。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
RUN_DIR="$ROOT/.run"
mkdir -p "$RUN_DIR"

# --- 运行环境：Node.js -------------------------------------------------------
NODE_BIN=""
for candidate in \
  "$HOME/.local/share/neoantigen/node/bin" \
  "$HOME/.local/share/uv/tools/node/bin" \
  "/opt/homebrew/bin" \
  "/usr/local/bin"; do
  if [ -x "$candidate/node" ]; then
    NODE_BIN="$candidate"
    break
  fi
done
if [ -z "$NODE_BIN" ]; then
  if command -v node >/dev/null 2>&1; then
    NODE_BIN="$(dirname "$(command -v node)")"
  else
    echo "错误：未找到 Node.js 运行时。" >&2
    exit 1
  fi
fi
export PATH="$NODE_BIN:$PATH"

# --- 依赖检查 ---------------------------------------------------------------
if [ ! -x "$BACKEND/.venv/bin/uvicorn" ]; then
  echo "错误：后端虚拟环境缺失（$BACKEND/.venv）。请参考 docs/development.md 创建。" >&2
  exit 1
fi
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "首次运行：安装前端依赖…"
  ( cd "$FRONTEND" && npm install )
fi

port_in_use() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# --- 后端 -------------------------------------------------------------------
if port_in_use 8000; then
  echo "后端已在 8000 端口运行。"
else
  # 清理陈旧/未监听端口的后端进程，避免多个进程共享同一 SQLite 造成锁冲突。
  if pgrep -f "uvicorn app.main:app" >/dev/null 2>&1; then
    echo "清理陈旧后端进程…"
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    for _ in $(seq 1 20); do
      pgrep -f "uvicorn app.main:app" >/dev/null 2>&1 || break
      sleep 0.5
    done
    pkill -9 -f "uvicorn app.main:app" 2>/dev/null || true
  fi
  echo "启动后端…"
  (
    cd "$BACKEND"
    DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./neoantigen.db}" \
      nohup ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 \
      > "$RUN_DIR/backend.log" 2>&1 &
    echo $! > "$RUN_DIR/backend.pid"
  )
fi

# --- 前端 -------------------------------------------------------------------
if port_in_use 3000; then
  echo "前端已在 3000 端口运行。"
else
  echo "启动前端…"
  (
    cd "$FRONTEND"
    NEXT_PUBLIC_API_URL="http://localhost:8000" \
      nohup npm run dev > "$RUN_DIR/frontend.log" 2>&1 &
    echo $! > "$RUN_DIR/frontend.pid"
  )
fi

# --- 等待就绪 ---------------------------------------------------------------
for _ in $(seq 1 40); do
  if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then break; fi
  sleep 1
done
for _ in $(seq 1 60); do
  if curl -sf http://localhost:3000/ >/dev/null 2>&1; then break; fi
  sleep 1
done

echo "平台已就绪：http://localhost:3000"
open "http://localhost:3000" >/dev/null 2>&1 || true
