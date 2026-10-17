# Architecture

```
┌──────────────┐   HTTP    ┌──────────────┐   SQL    ┌────────────┐
│  Frontend    │ ────────▶ │   Backend    │ ───────▶ │ PostgreSQL │
│  Next.js     │  /api/*   │   FastAPI    │          └────────────┘
│  :3000       │           │   :8000      │   cache  ┌────────────┐
└──────────────┘           └──────────────┘ ───────▶ │   Redis    │
                                                     └────────────┘
```

## Frontend (`frontend/`)

- Next.js App Router, React, TypeScript.
- TailwindCSS with design tokens defined as CSS variables in `app/globals.css`.
- shadcn/ui-style primitives live in `components/ui/`.
- A fixed 220px sidebar (`components/sidebar.tsx`) provides primary navigation.
- API access is centralized in `lib/api.ts`, configured via `NEXT_PUBLIC_API_URL`.

## Backend (`backend/`)

- FastAPI application factory in `app/main.py`.
- Configuration via `pydantic-settings` in `app/core/config.py`.
- SQLAlchemy 2.0 declarative models in `app/models/`.
- Pydantic schemas in `app/schemas/`.
- Routers in `app/api/routes/`, aggregated in `app/api/router.py`.
- Database session management in `app/db/session.py`.

## Database

- PostgreSQL is the production datastore.
- Schema is managed exclusively through Alembic migrations (`backend/alembic/`).
- The `Project` model is the only Phase 1 entity.

## Cache

- Redis is provisioned and wired via `REDIS_URL` for future asynchronous work
  (job queues, caching of analysis results). It is not yet used by any endpoint.

## Deployment

- `docker-compose.yml` runs `frontend`, `backend`, `postgres`, and `redis`.
- The backend container runs `alembic upgrade head` and seeds demo data before
  starting Uvicorn (see `backend/docker/entrypoint.sh`).
