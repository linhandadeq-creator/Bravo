#!/usr/bin/env bash
# Seed the database with the demo project.
set -euo pipefail

cd "$(dirname "$0")/../backend"

export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./neoantigen.db}"

if [ -d ".venv" ]; then
  PY=./.venv/bin/python
else
  PY=python3
fi

"$PY" -m app.seed
