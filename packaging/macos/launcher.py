"""Bravo desktop launcher (macOS bundle).

Opens a native window with a startup screen, starts the bundled FastAPI backend
(SQLite in ~/Library/Application Support/Bravo) and the prebuilt Next.js server,
then loads the UI in the same window. All runtimes are bundled inside the .app.
"""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import webview

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
_processes: list[subprocess.Popen] = []

LOADING_HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>
 body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
      font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text",sans-serif;
      background:#f5f6f8;color:#111}
 .box{text-align:center}
 h1{font-size:22px;font-weight:600;margin:0 0 10px}
 p{font-size:13px;color:#666;margin:6px 0}
 .bar{width:240px;height:3px;background:#e3e6ea;border-radius:2px;overflow:hidden;margin:18px auto 0}
 .bar i{display:block;height:100%;width:35%;background:#0a84ff;border-radius:2px;
        animation:slide 1.2s ease-in-out infinite}
 @keyframes slide{0%{transform:translateX(-100%)}100%{transform:translateX(320%)}}
</style></head><body><div class="box">
<h1>Bravo</h1><p id="status">正在启动本地服务…</p>
<p>首次启动约需 30–60 秒</p><div class="bar"><i></i></div>
</div></body></html>"""


def _log(name: str):
    return open(LOG_DIR / f"Bravo-{name}.log", "a", encoding="utf-8")


def _env() -> dict:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+pysqlite:///{(DATA_DIR / 'neoantigen.db').as_posix()}"
    env["STORAGE_DIR"] = str(DATA_DIR / "storage")
    env["PYTHONPATH"] = os.pathsep.join([str(SITE), str(BACKEND)])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["ENVIRONMENT"] = "production"
    return env


def _port_free(port: int) -> bool:
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _free_port(start: int) -> int:
    for port in range(start, start + 60):
        if _port_free(port):
            return port
    raise RuntimeError(f"no free port near {start}")


def _wait_http(url: str, timeout: float = 180.0) -> bool:
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


class Launcher:
    def __init__(self) -> None:
        self.window = webview.create_window(
            "Bravo",
            html=LOADING_HTML,
            width=1320,
            height=880,
            min_size=(960, 640),
        )
        self.window.events.closed += _shutdown

    def _status(self, text: str) -> None:
        try:
            self.window.evaluate_js(
                "document.getElementById('status').textContent = "
                + json.dumps(text)
            )
        except Exception:  # noqa: BLE001
            pass

    def _error(self, message: str) -> None:
        html = (
            "<!doctype html><html><head><meta charset='utf-8'><style>"
            "body{font-family:-apple-system, sans-serif;display:flex;align-items:center;"
            "justify-content:center;height:100vh;margin:0;background:#f5f6f8}"
            ".box{max-width:560px;text-align:center}h1{font-size:20px}"
            "p{color:#444;font-size:13px;line-height:1.6}code{background:#eee;padding:2px 5px;border-radius:4px}"
            "</style></head><body><div class='box'><h1>无法启动 Bravo</h1><p>"
            + message.replace("&", "&amp;").replace("<", "&lt;")
            + "</p><p>日志：<code>~/Library/Logs/Bravo-backend.log</code> · "
            "<code>~/Library/Logs/Bravo-frontend.log</code></p></div></body></html>"
        )
        try:
            self.window.load_html(html)
        except Exception:  # noqa: BLE001
            pass

    def boot(self) -> None:
        if not PYTHON.exists() or not NODE.exists():
            self._error("安装包缺少运行时文件，请重新安装。")
            return
        if not _port_free(BACKEND_PORT):
            self._error(
                "端口 8000 已被占用（可能另一个 Bravo 或开发服务器正在运行）。"
                "请先退出它，再重新打开 Bravo。"
            )
            return

        env = _env()
        self._status("正在初始化数据库…")
        _start("migrate", [str(PYTHON), "-m", "alembic", "upgrade", "head"], BACKEND, env).wait()
        _start("seed", [str(PYTHON), "-m", "app.seed"], BACKEND, env).wait()

        self._status("正在启动分析后端…")
        _start(
            "backend",
            [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
            BACKEND,
            env,
        )
        if not _wait_http(f"http://127.0.0.1:{BACKEND_PORT}/api/health"):
            self._error("分析后端未能启动。请查看日志后重试。")
            return

        self._status("正在启动界面服务…")
        frontend_port = _free_port(3000)
        frontend_env = os.environ.copy()
        frontend_env["PORT"] = str(frontend_port)
        frontend_env["HOSTNAME"] = "127.0.0.1"
        frontend_env["BACKEND_INTERNAL_URL"] = f"http://127.0.0.1:{BACKEND_PORT}"
        _start("frontend", [str(NODE), "server.js"], FRONTEND, frontend_env)
        if not _wait_http(f"http://127.0.0.1:{frontend_port}"):
            self._error("界面服务未能启动。请查看日志后重试。")
            return

        (DATA_DIR / "pids.json").write_text(
            json.dumps([p.pid for p in _processes if p.poll() is None])
        )
        self._status("即将进入…")
        self.window.load_url(f"http://127.0.0.1:{frontend_port}")

    def run(self) -> None:
        threading.Thread(target=self.boot, daemon=True).start()
        webview.start()


def main() -> int:
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: (_shutdown(), sys.exit(0)))
    Launcher().run()
    _shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
