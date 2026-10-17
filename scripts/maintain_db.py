#!/usr/bin/env python3
"""SQLite maintenance: report size/row counts, checkpoint the WAL and
(optionally) VACUUM to reclaim space.

This never deletes rows. ``--vacuum`` rewrites the database file compactly
(it needs free disk ~= current size and briefly locks the database), so run
it with the platform stopped.

Usage:
    python scripts/maintain_db.py                 # report + WAL checkpoint
    python scripts/maintain_db.py --vacuum        # also compact the file
    DATABASE_URL=sqlite+pysqlite:////path/db python scripts/maintain_db.py
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def resolve_db_path() -> Path:
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("sqlite"):
        # sqlite+pysqlite:///relative/path.db  or  sqlite:////abs/path.db
        raw = url.split("///", 1)[-1]
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = (ROOT / "backend" / candidate).resolve()
        return candidate
    return ROOT / "backend" / "neoantigen.db"


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def report(con: sqlite3.Connection, path: Path) -> None:
    print(f"database: {path}")
    print(f"file size: {human(path.stat().st_size)}")
    tables = [
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]
    total = 0
    for name in tables:
        count = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        total += count
        if count:
            print(f"  {name:<34}{count:>12}")
    print(f"  {'TOTAL':<34}{total:>12}")
    print(f"journal_mode: {con.execute('PRAGMA journal_mode').fetchone()[0]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vacuum", action="store_true", help="compact the file (reclaims space)")
    parser.add_argument("--db", type=Path, default=None, help="explicit database path")
    args = parser.parse_args()

    path = args.db or resolve_db_path()
    if not path.is_file():
        print(f"database not found: {path}", file=sys.stderr)
        return 1

    con = sqlite3.connect(str(path))
    try:
        report(con, path)
        before = path.stat().st_size
        if args.vacuum:
            print("running VACUUM (compacting; no rows are removed) ...")
            con.execute("VACUUM")
        print("checkpointing WAL ...")
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.commit()
        after = path.stat().st_size
        print(f"done. file size: {human(before)} -> {human(after)}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
