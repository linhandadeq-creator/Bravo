"""Deterministic mock evidence provider (demos and tests).

Every value is derived from the variant coordinates by a stable hash — clearly
labelled ``MOCK`` in status and provenance. It is never substituted for a real
provider.
"""
from __future__ import annotations

import hashlib

from app.evidence.base import (
    EvidenceQuery,
    EvidenceResult,
    EvidenceStatus,
    VariantEvidenceProvider,
)
from app.evidence.registry import register_evidence_provider

_SIGS = ("Pathogenic", "Likely pathogenic", "Uncertain significance", "Benign")
_DRIVERS = ("known-driver-mock",)


def _hash_digest(q: EvidenceQuery) -> int:
    key = f"{q.chromosome}|{q.position}|{q.reference}|{q.alternate}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


@register_evidence_provider
class MockEvidenceProvider(VariantEvidenceProvider):
    provider_name = "mock"
    provider_version = "1.0.0"
    is_mock = True
    description = (
        "Deterministic mock population/clinical evidence for demos and tests. "
        "Not real data."
    )
    supported_builds = ("GRCh37", "GRCh38")

    def health_check(self) -> EvidenceStatus:
        return EvidenceStatus.MOCK

    def query(self, q: EvidenceQuery) -> EvidenceResult:
        digest = _hash_digest(q)
        freq = round((digest % 1000) / 100000.0, 6)
        known_driver = digest % 7 == 0
        significance = _SIGS[digest % 4] if known_driver else None
        identifiers = []
        if known_driver:
            identifiers.append(f"COSMIC_MOCK_{(digest // 7) % 10000}")
        if digest % 3 == 0:
            identifiers.append(f"rs{(digest // 3) % 1000000000}")
        return EvidenceResult(
            provider=self.provider_name,
            source="mock-evidence-v1",
            provider_version=self.provider_version,
            population_frequency=freq,
            known_driver=known_driver,
            clinical_significance=significance,
            identifiers=identifiers,
            status=EvidenceStatus.MOCK.value,
            detail={"note": "Deterministic mock evidence; not real data."},
        )
