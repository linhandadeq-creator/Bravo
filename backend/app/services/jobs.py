"""In-process background job registry.

Single-node, thread-based execution for long-running one-click runs so the HTTP
request returns immediately and the client can poll for live stage progress and
request cancellation. Jobs are held in memory (suitable for the desktop/LAN
deployment); state is not shared across processes.
"""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

QUEUED = "QUEUED"
RUNNING = "RUNNING"
SUCCESS = "SUCCESS"
BLOCKED = "BLOCKED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"
_TERMINAL = {SUCCESS, BLOCKED, FAILED, CANCELLED}

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="one-click")


@dataclass
class Job:
    id: str
    status: str = QUEUED
    stages: list[dict] = field(default_factory=list)
    result: dict | None = None
    error: str | None = None
    cancel_requested: bool = False
    created_at: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def emit(self, step: str, status: str, detail: str | None = None) -> None:
        with self._lock:
            self.stages.append({"step": step, "status": status, "detail": detail})

    def set_status(self, status: str) -> None:
        with self._lock:
            self.status = status

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "id": self.id,
                "status": self.status,
                "stages": list(self.stages),
                "result": self.result,
                "error": self.error,
                "cancel_requested": self.cancel_requested,
            }


_JOBS: dict[str, Job] = {}
_JOBS_LOCK = threading.Lock()


def create_job() -> Job:
    job = Job(id=str(uuid.uuid4()))
    with _JOBS_LOCK:
        _JOBS[job.id] = job
    return job


def get_job(job_id: str) -> Job | None:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def request_cancel(job_id: str) -> Job | None:
    job = get_job(job_id)
    if job is not None:
        with job._lock:
            job.cancel_requested = True
    return job


def submit(job: Job, worker: Callable[[Job], None]) -> None:
    def _run() -> None:
        job.set_status(RUNNING)
        try:
            worker(job)
        except Exception as exc:  # noqa: BLE001 - record, never crash the executor
            with job._lock:
                job.status = FAILED
                job.error = str(exc)

    _EXECUTOR.submit(_run)


def is_terminal(status: str) -> bool:
    return status in _TERMINAL
