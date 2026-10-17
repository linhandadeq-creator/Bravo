"""Bravo portable launcher (Windows).

Starts the bundled FastAPI backend (SQLite in %LOCALAPPDATA%\\Bravo) and the
prebuilt Next.js server, then opens the default browser. Requires no system
Python or Node: both runtimes are bundled by the installer.

Run via the Start-menu / desktop shortcut, which uses ``runtime\\pythonw.exe``
so no console window is shown.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
PYTHON = ROOT / "runtime" / "python.exe"
NODE = ROOT / "node" / "node.exe"

DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Bravo"
LOG_DIR = DATA_DIR / "logs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_PORT = 8000
FRONTEND_PORT = 3000
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_processes: list[subprocess.Popen] = []


def _log(name: str):
    return open(LOG_DIR / f"{name}.log", "a", encoding="utf-8")


def _backend_env() -> dict:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+pysqlite:///{(DATA_DIR / 'neoantigen.db').as_posix()}"
    env["STORAGE_DIR"] = str(DATA_DIR / "storage")
    env["PYTHONPATH"] = str(BACKEND)
    env["ENVIRONMENT"] = "production"
    proteome = ROOT / "storage" / "proteomes" / "human_reviewed.fasta"
    if proteome.exists():
        env.setdefault("HUMAN_PROTEOME_FASTA", str(proteome))
    reference = ROOT / "storage" / "reference"
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
    log = _log(name)
    proc = subprocess.Popen(
        args,
        cwd=str(cwd),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )
    _processes.append(proc)
    return proc


def _save_pids() -> None:
    (DATA_DIR / "pids.json").write_text(
        json.dumps([p.pid for p in _processes if p.poll() is None])
    )


def main() -> int:
    if not PYTHON.exists() or not NODE.exists():
        _log("launcher").write("Missing bundled runtime (python/node).\n")
        return 1

    env = _backend_env()

    _start("migrate", [str(PYTHON), "-m", "alembic", "upgrade", "head"], BACKEND, env).wait()

    _start(
        "backend",
        [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
        BACKEND,
        env,
    )
    if not _wait_http(f"http://127.0.0.1:{BACKEND_PORT}/api/health"):
        _log("launcher").write("Backend did not become healthy; see backend.log\n")
        return 2

    frontend_env = os.environ.copy()
    frontend_env["PORT"] = str(FRONTEND_PORT)
    frontend_env["HOSTNAME"] = "127.0.0.1"
    frontend_env["BACKEND_INTERNAL_URL"] = f"http://127.0.0.1:{BACKEND_PORT}"
    _start("frontend", [str(NODE), "server.js"], FRONTEND, frontend_env)
    if not _wait_http(f"http://127.0.0.1:{FRONTEND_PORT}"):
        _log("launcher").write("Frontend did not start; see frontend.log\n")
        return 3

    _save_pids()
    webbrowser.open(f"http://127.0.0.1:{FRONTEND_PORT}")

    try:
        while True:
            time.sleep(2)
            if any(p.poll() is not None for p in _processes[1:]):
                break
    except KeyboardInterrupt:
        pass
    finally:
        for proc in _processes:
            if proc.poll() is None:
                proc.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
