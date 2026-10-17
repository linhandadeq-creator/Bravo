#!/usr/bin/env bash
set -e

echo "Waiting for database..."
python - <<'PY'
import time
import sys
from sqlalchemy import create_engine, text
from app.core.config import settings

for attempt in range(60):
    try:
        engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database is ready.")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"  attempt {attempt + 1}/60 failed: {exc}")
        time.sleep(2)
sys.exit("Database not reachable, giving up.")
PY

echo "Running migrations..."
alembic upgrade head

echo "Seeding demo data..."
python -m app.seed

echo "Starting API..."
exec "$@"
