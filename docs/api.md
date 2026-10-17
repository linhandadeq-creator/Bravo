# API Reference (Phase 1)

Base URL: `http://localhost:8000`. All application routes are prefixed with `/api`.
Interactive docs: `/docs` (Swagger UI) and `/redoc` (ReDoc).

## Health

### `GET /api/health`

```json
{ "status": "ok" }
```

## Projects

### `GET /api/projects`

Returns an array of projects, most recently created first.

### `POST /api/projects`

Request body:

```json
{
  "name": "Demo Cancer Project",
  "description": "Optional description",
  "status": "active"
}
```

Returns `201 Created` with the created project.

### `GET /api/projects/{project_id}`

Returns the project or `404 Not Found`.

### `PATCH /api/projects/{project_id}`

Accepts any subset of `name`, `description`, `status`.

## Project schema

```json
{
  "id": "uuid",
  "name": "string",
  "description": "string | null",
  "status": "string",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```
