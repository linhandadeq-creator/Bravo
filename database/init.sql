-- Initialization script for the neoantigen PostgreSQL database.
-- Executed automatically by the postgres image on first startup.
-- Schema objects are managed by Alembic migrations.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
