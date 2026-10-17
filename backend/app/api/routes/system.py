from fastapi import APIRouter

from app.services.manifest import system_manifest
from app.services.self_filter import status as self_filter_status

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/manifest")
def get_manifest() -> dict:
    return system_manifest()


@router.get("/self-filter")
def get_self_filter() -> dict:
    return self_filter_status()
