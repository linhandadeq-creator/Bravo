# Phase 1 — Foundation

## In scope

- Project skeleton and directory layout.
- Next.js UI shell with sidebar and pages: Dashboard, Projects, Variants,
  Neoantigens, Simulation, Reports, Settings.
- FastAPI service with `/api/health` and `/api/projects` (GET/POST/GET by id).
- `Project` model + Alembic migration.
- PostgreSQL and Redis provisioning via Docker Compose.
- Demo project seeding (`Demo Cancer Project`).
- Backend test suite.

## Out of scope (later phases)

- VCF parsing and validation.
- Variant annotation.
- HLA typing.
- Neoantigen prediction.
- mRNA sequence design.

These areas are represented in the UI by explicit "planned for a later phase"
placeholders so the navigation surface is complete without pretending the
functionality exists.
