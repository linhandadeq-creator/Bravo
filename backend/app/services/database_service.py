"""Database inspection and selective deletion (local research maintenance).

Exposes read-only table browsing and user-driven row deletion over the
SQLAlchemy metadata (no arbitrary SQL). Deletions rely on the SQLite
``ON DELETE CASCADE`` foreign keys, so removing a project/run also removes its
children. This is a maintenance tool for the operator's own data.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import Base, run_write_with_retry

MAX_TEXT_PREVIEW = 400
MAX_DELETE_IDS = 5000


class DatabaseError(RuntimeError):
    pass


class UnknownTableError(DatabaseError):
    pass


def _table(name: str):
    table = Base.metadata.tables.get(name)
    if table is None:
        raise UnknownTableError(f"Unknown table '{name}'.")
    return table


def _sqlite_path() -> Path | None:
    url = settings.DATABASE_URL
    if not url.startswith("sqlite"):
        return None
    raw = url.split("///", 1)[-1]
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    return candidate


def _serialize(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if isinstance(value, str) and len(value) > MAX_TEXT_PREVIEW:
        return value[:MAX_TEXT_PREVIEW] + f"… (+{len(value) - MAX_TEXT_PREVIEW} chars)"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, default=str)
        if len(text) > MAX_TEXT_PREVIEW:
            return text[:MAX_TEXT_PREVIEW] + "…"
        return value
    return value


def overview(db: Session) -> dict:
    path = _sqlite_path()
    file_bytes = wal_bytes = 0
    journal_mode = None
    if path is not None:
        if path.is_file():
            file_bytes = path.stat().st_size
        for suffix in ("-wal", "-shm"):
            extra = Path(str(path) + suffix)
            if extra.is_file():
                wal_bytes += extra.stat().st_size
        try:
            journal_mode = db.execute(text("PRAGMA journal_mode")).scalar()
        except Exception:  # noqa: BLE001
            journal_mode = None

    tables = list_tables(db)
    total_rows = sum(t["rows"] for t in tables)
    return {
        "engine": "sqlite" if path is not None else settings.DATABASE_URL.split(":", 1)[0],
        "database_file": str(path) if path else None,
        "file_size_bytes": file_bytes,
        "wal_size_bytes": wal_bytes,
        "journal_mode": journal_mode,
        "table_count": len(tables),
        "total_rows": total_rows,
    }


def list_tables(db: Session) -> list[dict]:
    tables = []
    for name, table in Base.metadata.tables.items():
        rows = db.execute(select(func.count()).select_from(table)).scalar() or 0
        tables.append({"name": name, "rows": int(rows)})
    tables.sort(key=lambda item: item["name"])
    return tables


def table_rows(
    db: Session, name: str, limit: int = 50, offset: int = 0
) -> dict:
    table = _table(name)
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    total = db.execute(select(func.count()).select_from(table)).scalar() or 0
    pk = [c.name for c in table.primary_key.columns]
    order = pk[0] if pk else next(iter(table.columns)).name
    stmt = select(table).order_by(table.c[order]).limit(limit).offset(offset)
    rows = [
        {key: _serialize(value) for key, value in row._mapping.items()}
        for row in db.execute(stmt)
    ]
    return {
        "name": name,
        "columns": [c.name for c in table.columns],
        "primary_key": pk,
        "total": int(total),
        "limit": limit,
        "offset": offset,
        "rows": rows,
    }


def delete_rows(db: Session, name: str, ids: list[str]) -> int:
    table = _table(name)
    pk_cols = [c.name for c in table.primary_key.columns]
    if len(pk_cols) != 1:
        raise DatabaseError(f"Table '{name}' has a composite primary key.")
    if not ids:
        raise DatabaseError("No rows selected.")
    if len(ids) > MAX_DELETE_IDS:
        raise DatabaseError(f"Too many rows selected (max {MAX_DELETE_IDS}).")
    pk = table.c[pk_cols[0]]

    def _do() -> int:
        result = db.execute(table.delete().where(pk.in_(ids)))
        return result.rowcount or 0

    return run_write_with_retry(db, _do)


def clear_table(db: Session, name: str) -> int:
    table = _table(name)

    def _do() -> int:
        result = db.execute(table.delete())
        return result.rowcount or 0

    return run_write_with_retry(db, _do)
