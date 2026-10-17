from fastapi import APIRouter

from app.api.routes import (
    analysis_runs,
    annotation,
    assembly,
    constructs,
    database,
    evidence,
    health,
    integration,
    generate,
    neoantigen,
    project_extras,
    projects,
    reports,
    system,
    validation,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(project_extras.router)
api_router.include_router(analysis_runs.router)
api_router.include_router(annotation.router)
api_router.include_router(evidence.router)
api_router.include_router(integration.router)
api_router.include_router(neoantigen.router)
api_router.include_router(assembly.router)
api_router.include_router(constructs.router)
api_router.include_router(validation.router)
api_router.include_router(reports.router)
api_router.include_router(generate.router)
api_router.include_router(database.router)
api_router.include_router(system.router)
