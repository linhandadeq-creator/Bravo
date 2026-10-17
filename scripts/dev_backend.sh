#!/usr/bin/env bash
# Start the FastAPI backend for local development.
set -euo pipefail

cd "$(dirname "$0")/../backend"

if [ ! -d ".venv" ]; then
  PYTHON_BIN="${PYTHON_BIN:-}"
  if [ -z "$PYTHON_BIN" ]; then
    for candidate in python3.12 python3.11 python3; do
      if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
      fi
    done
  fi
  if [ -z "$PYTHON_BIN" ]; then
    echo "No suitable Python interpreter found (need 3.11+)." >&2
    exit 1
  fi
  "$PYTHON_BIN" -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -r requirements.txt
fi

export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./neoantigen.db}"

./.venv/bin/alembic upgrade head
./.venv/bin/python -m app.seed
exec ./.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port "${BACKEND_PORT:-8000}"
