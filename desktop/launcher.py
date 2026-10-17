#!/usr/bin/env python3
"""Bravo desktop application launcher.

Starts the local FastAPI backend (SQLite, user data dir) and the built Next.js
frontend, then opens a native window pointing at the UI. Designed to run from a
macOS ``.app`` bundle so the platform behaves like a real desktop application
(no browser chrome).
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

DATA_DIR = Path.home() / "Library" / "Application Support" / "Bravo"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_PORT = int(os.environ.get("BRAVO_BACKEND_PORT", "8000"))
FRONTEND_PORT = int(os.environ.get("BRAVO_FRONTEND_PORT", "3000"))

_processes: list[subprocess.Popen] = []


def _node() -> str:
    candidate = Path.home() / ".local" / "share" / "neoantigen" / "node" / "bin" / "node"
    if candidate.exists():
        return str(candidate)
    return "node"


def _backend_env() -> dict:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+pysqlite:///{DATA_DIR / 'neoantigen.db'}"
    env["STORAGE_DIR"] = str(DATA_DIR / "storage")
    proteome = BACKEND / "storage" / "proteomes" / "human_reviewed.fasta"
    if proteome.exists():
        env.setdefault("HUMAN_PROTEOME_FASTA", str(proteome))
    offline = BACKEND / "storage" / "reference"
    if offline.exists():
        env.setdefault("OFFLINE_REFERENCE_DIR", str(offline))
    return env


def _wait_http(url: str, timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.4)
    return False


def _migrate_and_seed() -> None:
    python = str(BACKEND / ".venv" / "bin" / "python")
    env = _backend_env()
    subprocess.run(
        [python, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND),
        env=env,
        check=False,
    )
    subprocess.run(
        [python, "-m", "app.seed"], cwd=str(BACKEND), env=env, check=False
    )


def start_services() -> None:
    if not (BACKEND / ".venv" / "bin" / "uvicorn").exists():
        sys.exit("Backend virtualenv missing. Run scripts/start_platform.sh once.")
    if not (FRONTEND / ".next").exists():
        sys.exit("Frontend is not built. Run scripts/build_desktop_app.sh.")

    _migrate_and_seed()

    backend = subprocess.Popen(
        [
            str(BACKEND / ".venv" / "bin" / "uvicorn"),
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(BACKEND_PORT),
        ],
        cwd=str(BACKEND),
        env=_backend_env(),
        start_new_session=True,
    )
    _processes.append(backend)

    frontend_env = os.environ.copy()
    frontend_env["NEXT_PUBLIC_API_URL"] = f"http://127.0.0.1:{BACKEND_PORT}"
    frontend = subprocess.Popen(
        [
            _node(),
            str(FRONTEND / "node_modules" / ".bin" / "next"),
            "start",
            "-H",
            "127.0.0.1",
            "-p",
            str(FRONTEND_PORT),
        ],
        cwd=str(FRONTEND),
        env=frontend_env,
        start_new_session=True,
    )
    _processes.append(frontend)


def shutdown(*_args) -> None:
    for process in _processes:
        if process.poll() is None:
            process.terminate()
    for process in _processes:
        try:
            process.wait(timeout=8)
        except Exception:  # noqa: BLE001
            process.kill()
    _processes.clear()


def _reachable(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:  # noqa: BLE001
        return False


def _open_url(url: str) -> None:
    try:
        subprocess.run(["open", url], check=False)
    except Exception:  # noqa: BLE001
        import webbrowser  # noqa: PLC0415

        webbrowser.open(url)


def _wait_forever() -> None:
    try:
        while True:
            time.sleep(1)
    finally:
        shutdown()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--window", action="store_true", help="use the native webview window"
    )
    parser.add_argument(
        "--browser", action="store_true", help="open the UI in the default browser"
    )
    parser.add_argument("--no-window", action="store_true", help="run services only")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, lambda *a: (shutdown(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda *a: (shutdown(), sys.exit(0)))

    url = f"http://127.0.0.1:{FRONTEND_PORT}"
    backend_up = _reachable(f"http://127.0.0.1:{BACKEND_PORT}/api/health")
    frontend_up = _reachable(url)
    already_running = backend_up and frontend_up

    if not already_running:
        start_services()
        backend_ok = _wait_http(f"http://127.0.0.1:{BACKEND_PORT}/api/health")
        frontend_ok = _wait_http(url)
        print(
            f"backend={'ok' if backend_ok else 'down'} "
            f"frontend={'ok' if frontend_ok else 'down'}",
            flush=True,
        )
    else:
        print("[bravo] services already running", flush=True)

    if args.no_window:
        _wait_forever()
        return 0

    if args.window:
        try:
            import traceback  # noqa: PLC0415

            import webview  # noqa: PLC0415

            print(f"[bravo] opening window -> {url}", flush=True)
            webview.create_window(
                "Bravo", url, width=1280, height=860, min_size=(980, 680)
            )
            webview.start()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            print("[bravo] webview failed; opening browser instead", flush=True)
            _open_url(url)
            _wait_forever()
        else:
            shutdown()
        return 0

    # Default: open the UI in the system browser (reliable on all macOS versions).
    # The services run in their own session, so they keep running after this
    # launcher exits. Stop them with scripts/stop_platform.sh.
    print(f"[bravo] opening browser -> {url}", flush=True)
    _open_url(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
