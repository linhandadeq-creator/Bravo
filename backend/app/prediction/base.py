"""Prediction provider interface.

The platform never hardcodes a specific prediction tool. Providers implement
this interface and register themselves; a ``mock`` provider is available for
demos/tests and real research tools plug in through an adapter.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class ProviderStatus(str, Enum):
    MOCK = "MOCK"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class ProviderUnavailableError(RuntimeError):
    pass


@dataclass
class PredictionInput:
    candidate_id: str
    peptide: str | None
    peptide_representation: str
    hla_allele: str
    gene: str | None = None
    protein_change: str | None = None
    # Position of the mutated residue within `peptide` (0-based), used by
    # providers to enumerate epitope windows that contain the mutation.
    mutation_offset: int | None = None


@dataclass
class PredictionOutput:
    candidate_id: str
    hla: str
    prediction_value: float | None
    metric_name: str
    status: str
    provider: str
    provider_version: str
    input_hash: str
    detail: dict = field(default_factory=dict)


@dataclass
class ValidationResult:
    ok: bool
    reason: str | None = None


class PredictionProvider(ABC):
    provider_name: str = "base"
    provider_version: str = "0.0.0"
    is_mock: bool = False
    description: str = ""

    def __init__(self, reference_build: str | None = None) -> None:
        self.reference_build = reference_build

    @abstractmethod
    def supported_hla(self) -> list[str]:
        """Return supported HLA alleles (``["*"]`` means any)."""

    @abstractmethod
    def health_check(self) -> ProviderStatus:
        """Return the current provider status."""

    @abstractmethod
    def validate_input(self, inputs: list[PredictionInput]) -> ValidationResult:
        """Validate a batch of prediction inputs before running."""

    @abstractmethod
    def predict(self, inputs: list[PredictionInput]) -> list[PredictionOutput]:
        """Run prediction. Must never silently substitute another provider."""
