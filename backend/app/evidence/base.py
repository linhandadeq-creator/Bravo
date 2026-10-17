"""Variant evidence provider interface.

The platform never hardcodes a single evidence database. Providers implement
this interface and register themselves; a deterministic ``mock`` provider is
available for demos/tests, and real databases (gnomAD, ClinVar, COSMIC) plug
in as providers. Population frequency, known-driver and clinical-significance
evidence is always recorded with full provenance; a failed lookup is never
silently replaced by mock data.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class EvidenceStatus(str, Enum):
    MOCK = "MOCK"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class EvidenceUnavailableError(RuntimeError):
    pass


@dataclass
class EvidenceQuery:
    chromosome: str | None
    position: int | None
    reference: str | None
    alternate: str | None
    reference_build: str


@dataclass
class EvidenceResult:
    provider: str
    source: str
    provider_version: str
    population_frequency: float | None = None
    known_driver: bool | None = None
    clinical_significance: str | None = None
    identifiers: list[str] = field(default_factory=list)
    status: str = EvidenceStatus.AVAILABLE.value
    detail: dict = field(default_factory=dict)


class VariantEvidenceProvider(ABC):
    provider_name: str = "base"
    provider_version: str = "0.0.0"
    is_mock: bool = False
    description: str = ""
    supported_builds: tuple[str, ...] = ("GRCh37", "GRCh38")

    @abstractmethod
    def health_check(self) -> EvidenceStatus:
        """Return whether the provider is usable right now."""

    @abstractmethod
    def query(self, q: EvidenceQuery) -> EvidenceResult:
        """Look up evidence for a single variant.

        Raises ``EvidenceUnavailableError`` when the provider cannot serve the
        query (offline, license missing, network failure). Never returns mock
        data for a real provider.
        """
