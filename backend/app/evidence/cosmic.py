"""COSMIC known-driver provider (reserved).

COSMIC requires a commercial licence and is not redistributable. The adapter
slot is registered so the platform reports it explicitly as UNAVAILABLE; a
licensed installation can implement ``COSMIC_LOGIN`` / ``COSMIC_PASSWORD``
credentials against the COSMIC API in a future release.
"""
from __future__ import annotations

from app.evidence.base import (
    EvidenceQuery,
    EvidenceResult,
    EvidenceStatus,
    EvidenceUnavailableError,
    VariantEvidenceProvider,
)
from app.evidence.registry import register_evidence_provider


@register_evidence_provider
class CosmicEvidenceProvider(VariantEvidenceProvider):
    provider_name = "cosmic"
    provider_version = "reserved"
    is_mock = False
    description = (
        "COSMIC known cancer-mutation evidence — reserved adapter; requires a "
        "commercial COSMIC licence."
    )
    supported_builds = ("GRCh37", "GRCh38")

    def health_check(self) -> EvidenceStatus:
        return EvidenceStatus.UNAVAILABLE

    def query(self, q: EvidenceQuery) -> EvidenceResult:
        raise EvidenceUnavailableError(
            "COSMIC is not licensed/configured on this installation."
        )
