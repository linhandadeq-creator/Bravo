# Docker

Helper assets for the containerized runtime. `docker-compose.yml` at the
repository root orchestrates four services:

| Service    | Image / build        | Port |
| ---------- | -------------------- | ---- |
| `frontend` | `./frontend`         | 3000 |
| `backend`  | `./backend`          | 8000 |
| `postgres` | `postgres:16-alpine` | 5432 |
| `redis`    | `redis:7-alpine`     | 6379 |

## Usage

```bash
cp ../.env.example ../.env
docker compose up --build
```

The backend entrypoint (`backend/docker/entrypoint.sh`) waits for PostgreSQL,
applies Alembic migrations, seeds the demo project, and launches Uvicorn.

## Reset

```bash
docker compose down -v   # removes the postgres volume
```
