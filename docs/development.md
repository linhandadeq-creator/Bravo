# Development

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16 (optional for backend-only work; SQLite is supported via `DATABASE_URL`)
- Redis 7 (optional for Phase 1)

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Local database. PostgreSQL via Docker:
export DATABASE_URL=postgresql+psycopg2://neoantigen:neoantigen@localhost:5432/neoantigen
# ...or SQLite for a quick, dependency-free run:
# export DATABASE_URL=sqlite+pysqlite:///./neoantigen.db

alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

## Frontend

```bash
cd frontend
npm install
export NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Then open http://localhost:3000.

## 一键启动 / 桌面入口（macOS）

```bash
./scripts/start_platform.sh    # 自动启动后端 + 前端并打开浏览器
./scripts/stop_platform.sh     # 停止
./scripts/install_desktop.sh   # 在桌面创建「Bravo.app」双击入口
```

`start_platform.sh` 会优先使用 `~/.local/share/neoantigen/node` 下的 Node，
其次系统 Node；日志与进程号写入 `.run/`。

## Tests

```bash
cd backend
pytest
```

## Lint / typecheck

```bash
cd frontend
npm run lint
npm run typecheck
```
