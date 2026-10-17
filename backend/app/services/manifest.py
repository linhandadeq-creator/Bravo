"""System/tool manifest for reproducibility and provenance."""
from __future__ import annotations

import platform
from importlib.metadata import PackageNotFoundError, version

from app.annotation.offline import clinvar_status
from app.annotation.registry import list_providers
from app.core.config import settings
from app.core.reference import SUPPORTED_REFERENCE_BUILDS
from app.evidence.registry import list_evidence_providers
from app.prediction.registry import list_prediction_providers
from app.services.evidence import status as evidence_status
from app.services.self_filter import status as self_filter_status
from app.services.somatic_calling import status as somatic_calling_status

_PACKAGES = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "alembic",
    "pysam",
    "mhcflurry",
    "torch",
    "numpy",
    "pandas",
    "reportlab",
    "httpx",
]


def _version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None
    except Exception:  # noqa: BLE001
        return None


def tool_versions() -> dict:
    return {
        "app_version": settings.APP_VERSION,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {name: _version(name) for name in _PACKAGES},
    }


def system_manifest() -> dict:
    return {
        "tools": tool_versions(),
        "reference_builds": list(SUPPORTED_REFERENCE_BUILDS),
        "annotation_providers": list_providers(),
        "prediction_providers": list_prediction_providers(),
        "variant_evidence_providers": list_evidence_providers(),
        "self_filter": self_filter_status(),
        "ms_evidence": evidence_status(),
        "clinvar": clinvar_status(),
        "somatic_calling": somatic_calling_status(),
    }
