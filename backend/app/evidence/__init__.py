"""Variant evidence engine: population / known-driver / clinical significance."""
from app.evidence.registry import (
    available_evidence_providers,
    get_evidence_provider,
    list_evidence_providers,
)

__all__ = [
    "available_evidence_providers",
    "get_evidence_provider",
    "list_evidence_providers",
]
