"""SQLite locking regression tests.

Covers the upload sample-insert path, concurrent writers, the bounded
lock-retry helper and connection recovery after an error.
"""
from __future__ import annotations

import threading
import uuid

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, is_lock_contention, run_write_with_retry
from app.models.analysis_run import AnalysisRun
from app.models.project import Project
from app.models.sample import TUMOR, Sample


def _upload(client, project_id: str, dataset) -> object:
    with open(dataset["tumor"], "rb") as tumor, open(dataset["normal"], "rb") as normal:
        return client.post(
            "/api/analysis-runs/upload",
            data={"project_id": project_id, "reference_build": "GRCh38"},
            files={
                "tumor_file": ("tumor.vcf", tumor, "text/plain"),
                "normal_file": ("normal.vcf", normal, "text/plain"),
            },
        )


def test_sequential_uploads_create_complete_samples_without_duplicates(
    client, annotation_dataset
):
    project_id = client.post("/api/projects", json={"name": "Seq Uploads"}).json()["id"]
    for _ in range(3):
        response = _upload(client, project_id, annotation_dataset)
        assert response.status_code == 201, response.text

    samples = client.get(f"/api/projects/{project_id}/samples").json()
    # Each upload registers a tumor + a normal sample (3 × 2).
    assert len(samples) == 6
    ids = [s["id"] for s in samples]
    assert len(ids) == len(set(ids)), "duplicate sample records"
    assert all(s["original_filename"] for s in samples), "incomplete sample record"
    assert all(s["file_size_bytes"] for s in samples), "missing size"

    runs = client.get("/api/analysis-runs", params={"project_id": project_id}).json()
    assert len(runs) == 3
    assert all(r["tumor_sample_id"] and r["normal_sample_id"] for r in runs)


def test_upload_recovers_after_error(client, annotation_dataset):
    # A bad request must not poison the session/connection.
    missing = client.post(
        "/api/analysis-runs/upload",
        data={"project_id": "does-not-exist", "reference_build": "GRCh38"},
        files={"tumor_file": ("tumor.vcf", b"x", "text/plain")},
    )
    assert missing.status_code == 404

    project_id = client.post("/api/projects", json={"name": "Recovery"}).json()["id"]
    recovered = _upload(client, project_id, annotation_dataset)
    assert recovered.status_code == 201, recovered.text


# ---- engine pragmas + concurrent writers on a file database ------------------


def _file_engine(tmp_path, wal: bool = True):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path/'test.db'}",
        connect_args={"check_same_thread": False, "timeout": 30.0},
    )

    @event.listens_for(engine, "connect")
    def _configure(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        if wal:
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


def test_sqlite_pragmas_applied(tmp_path):
    engine = _file_engine(tmp_path)
    with engine.connect() as connection:
        mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar()
        busy = connection.exec_driver_sql("PRAGMA busy_timeout").scalar()
        fk = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
    assert str(mode).lower() == "wal"
    assert int(busy) == 30000
    assert int(fk) == 1


def test_concurrent_sample_writes_do_not_lock_error(tmp_path):
    engine = _file_engine(tmp_path)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session() as setup:
        project = Project(name="Concurrent")
        setup.add(project)
        setup.commit()
        project_id = project.id

    workers = 8
    per_worker = 6
    errors: list[Exception] = []

    def worker(index: int) -> None:
        try:
            for n in range(per_worker):
                session = Session()
                try:
                    run_write_with_retry(
                        session,
                        lambda: session.add(
                            Sample(
                                id=str(uuid.uuid4()),
                                project_id=project_id,
                                name=f"t{index}-{n}",
                                sample_type=TUMOR,
                                source="UPLOAD",
                            )
                        ),
                    )
                finally:
                    session.close()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, f"concurrent writers raised: {errors[:3]}"
    with Session() as check:
        total = check.execute(select(func.count(Sample.id))).scalar()
    assert total == workers * per_worker


def test_concurrent_full_run_analysis_no_lock_error(tmp_path, annotation_dataset):
    """Run the whole upload persistence (samples + run + variants) concurrently
    on a file database with the production pragmas."""
    from app.models.variant import Variant
    from app.services.analysis import run_analysis

    engine = _file_engine(tmp_path)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session() as setup:
        project = Project(name="Concurrent Analysis")
        setup.add(project)
        setup.commit()
        project_id = project.id

    def build_sample(role: str, index: int) -> Sample:
        return Sample(
            id=str(uuid.uuid4()),
            project_id=project_id,
            name=f"{role}-{index}",
            sample_type=TUMOR if role == "tumor" else "NORMAL",
            reference_build="GRCh38",
            storage_path=annotation_dataset[role],
            file_size_bytes=1,
            source="UPLOAD",
        )

    runs = 6
    errors: list[Exception] = []

    def worker(index: int) -> None:
        session = Session()
        try:
            run = run_analysis(
                session,
                project_id=project_id,
                tumor_sample=build_sample("tumor", index),
                normal_sample=build_sample("normal", index),
                reference_build="GRCh38",
            )
            assert run.id
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(runs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, f"concurrent run_analysis raised: {errors[:3]}"
    with Session() as check:
        run_count = check.execute(select(func.count(AnalysisRun.id))).scalar()
        sample_count = check.execute(select(func.count(Sample.id))).scalar()
        variant_count = check.execute(select(func.count(Variant.id))).scalar()
    assert run_count == runs
    assert sample_count == runs * 2  # tumor + normal per run
    assert variant_count > 0  # variants were persisted


# ---- bounded retry helper ----------------------------------------------------


class _FakeSession:
    def __init__(self, failures: int, message: str = "database is locked"):
        self.calls = 0
        self.rollbacks = 0
        self._failures = failures
        self._message = message

    def commit(self):
        self.calls += 1
        if self.calls <= self._failures:
            raise OperationalError("COMMIT", {}, Exception(self._message))

    def rollback(self):
        self.rollbacks += 1


def test_retry_retries_transient_lock_then_succeeds():
    session = _FakeSession(failures=2)
    calls = []
    run_write_with_retry(
        session, lambda: calls.append(1), attempts=5, base_delay=0.0
    )
    assert session.calls == 3  # two collisions + success
    assert session.rollbacks == 2
    assert len(calls) == 3  # the write unit re-ran each attempt


def test_retry_gives_up_after_attempts():
    session = _FakeSession(failures=99)
    with pytest.raises(OperationalError):
        run_write_with_retry(session, lambda: None, attempts=3, base_delay=0.0)
    assert session.calls == 3


def test_retry_does_not_mask_other_operational_errors():
    session = _FakeSession(failures=99, message="no such table: nope")
    with pytest.raises(OperationalError):
        run_write_with_retry(session, lambda: None, attempts=5, base_delay=0.0)
    assert session.calls == 1  # non-lock error raised immediately


def test_is_lock_contention_classification():
    assert is_lock_contention(OperationalError("x", {}, Exception("database is locked")))
    assert is_lock_contention(
        OperationalError("x", {}, Exception("database table is locked: samples"))
    )
    assert not is_lock_contention(
        OperationalError("x", {}, Exception("no such table: samples"))
    )
