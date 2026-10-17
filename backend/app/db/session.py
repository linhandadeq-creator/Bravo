from collections.abc import Generator
import time

from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# SQLite serialises writers. Without a busy timeout a competing writer fails
# immediately with "database is locked"; a bounded wait lets short write
# transactions drain instead. The sqlite3 connect timeout (seconds) and the
# PRAGMA busy_timeout (milliseconds) are both set.
_busy_timeout_ms = max(0, int(getattr(settings, "SQLITE_BUSY_TIMEOUT_MS", 30000)))
_wal_enabled = bool(getattr(settings, "SQLITE_WAL", True))

connect_args = (
    {"check_same_thread": False, "timeout": _busy_timeout_ms / 1000.0}
    if _is_sqlite
    else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)


if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        # SQLite does not enforce foreign keys by default; enable so that
        # ON DELETE CASCADE (which the models rely on) actually works.
        cursor.execute("PRAGMA foreign_keys=ON")
        # Bounded wait for a competing writer instead of failing instantly.
        cursor.execute(f"PRAGMA busy_timeout={_busy_timeout_ms}")
        if _wal_enabled:
            # WAL improves reader/writer concurrency (local filesystems). It
            # does not lift the single-writer restriction.
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# SQLite error strings that indicate transient lock contention (only these are
# retried — every other OperationalError is surfaced unchanged).
_LOCKED_MARKERS = (
    "database is locked",
    "database table is locked",
    "database schema is locked",
)


def is_lock_contention(exc: BaseException) -> bool:
    message = str(getattr(exc, "orig", exc)).lower()
    return any(marker in message for marker in _LOCKED_MARKERS)


def run_write_with_retry(
    db: Session,
    write_fn,
    *,
    attempts: int = 5,
    base_delay: float = 0.2,
):
    """Run a self-contained write unit with bounded exponential-backoff retry.

    ``write_fn`` must (re)create its ORM objects and flush them; it is called
    again after a rolled-back lock collision, so it must not rely on session
    state from a previous attempt. Non-lock errors are re-raised immediately.
    """
    delay = base_delay
    for attempt in range(1, attempts + 1):
        try:
            result = write_fn()
            db.commit()
            return result
        except OperationalError as exc:
            db.rollback()
            if not is_lock_contention(exc) or attempt >= attempts:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")  # pragma: no cover


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
