"""Bravo desktop launcher (macOS bundle).

Starts the bundled FastAPI backend (SQLite in ~/Library/Application Support/Bravo)
and the prebuilt Next.js server, then opens the default browser. All runtimes
are bundled inside the .app; no system Python/Node is required.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

RESOURCES = Path(__file__).resolve().parent
APP = RESOURCES / "app"
BACKEND = APP / "backend"
FRONTEND = APP / "frontend"
PYTHON = RESOURCES / "runtime" / "bin" / "python3"
NODE = RESOURCES / "node" / "bin" / "node"
SITE = RESOURCES / "site-packages"

DATA_DIR = Path.home() / "Library" / "Application Support" / "Bravo"
LOG_DIR = Path.home() / "Library" / "Logs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_PORT = 8000
FRONTEND_PORT = 3000
_processes: list[subprocess.Popen] = []


def _log(name: str):
    return open(LOG_DIR / f"Bravo-{name}.log", "a", encoding="utf-8")


def _env() -> dict:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+pysqlite:///{(DATA_DIR / 'neoantigen.db').as_posix()}"
    env["STORAGE_DIR"] = str(DATA_DIR / "storage")
    env["PYTHONPATH"] = os.pathsep.join([str(SITE), str(BACKEND)])
    env["ENVIRONMENT"] = "production"
    proteome = RESOURCES / "storage" / "proteomes" / "human_reviewed.fasta"
    if proteome.exists():
        env.setdefault("HUMAN_PROTEOME_FASTA", str(proteome))
    reference = RESOURCES / "storage" / "reference"
    if reference.exists():
        env.setdefault("OFFLINE_REFERENCE_DIR", str(reference))
    return env


def _wait_http(url: str, timeout: float = 120.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    return False


def _start(name: str, args: list[str], cwd: Path, env: dict) -> subprocess.Popen:
    proc = subprocess.Popen(
        args,
        cwd=str(cwd),
        env=env,
        stdout=_log(name),
        stderr=subprocess.STDOUT,
    )
    _processes.append(proc)
    return proc


def _shutdown(*_args) -> None:
    for proc in _processes:
        if proc.poll() is None:
            proc.terminate()
    for proc in _processes:
        try:
            proc.wait(timeout=8)
        except Exception:  # noqa: BLE001
            proc.kill()
    _processes.clear()


def main() -> int:
    if not PYTHON.exists() or not NODE.exists():
        _log("launcher").write("Missing bundled runtime.\n")
        return 1
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, lambda *_: (_shutdown(), sys.exit(0)))

    env = _env()
    _start("migrate", [str(PYTHON), "-m", "alembic", "upgrade", "head"], BACKEND, env).wait()
    _start("seed", [str(PYTHON), "-m", "app.seed"], BACKEND, env).wait()
    _start(
        "backend",
        [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
        BACKEND,
        env,
    )
    if not _wait_http(f"http://127.0.0.1:{BACKEND_PORT}/api/health"):
        return 2

    frontend_env = os.environ.copy()
    frontend_env["PORT"] = str(FRONTEND_PORT)
    frontend_env["HOSTNAME"] = "127.0.0.1"
    frontend_env["BACKEND_INTERNAL_URL"] = f"http://127.0.0.1:{BACKEND_PORT}"
    _start("frontend", [str(NODE), "server.js"], FRONTEND, frontend_env)
    if not _wait_http(f"http://127.0.0.1:{FRONTEND_PORT}"):
        return 3

    (DATA_DIR / "pids.json").write_text(json.dumps([p.pid for p in _processes if p.poll() is None]))
    webbrowser.open(f"http://127.0.0.1:{FRONTEND_PORT}")

    try:
        while True:
            time.sleep(2)
            if any(p.poll() is not None for p in _processes[2:]):
                break
    finally:
        _shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
