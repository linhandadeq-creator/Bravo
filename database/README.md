# Database

This directory holds database-related assets.

- `init.sql` — bootstrap SQL mounted into the PostgreSQL container on first start.
- Schema objects (currently the `projects` table) are created by Alembic migrations located in `backend/alembic/versions/`.

## Migrations

Run from the `backend/` directory:

```bash
alembic upgrade head       # apply migrations
alembic revision --autogenerate -m "message"   # create a new migration
alembic downgrade -1       # roll back one migration
```
