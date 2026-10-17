"""Plugin interface for variant annotation providers.

Every provider implements :class:`VariantAnnotator` and declares its
:class:`ProviderMetadata` (reference build, annotation version, transcript
source). The engine validates that metadata against the analysis run before any
annotation is accepted.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class Consequence(str, Enum):
    MISSENSE = "missense"
    FRAMESHIFT = "frameshift"
    STOP_GAINED = "stop_gained"
    STOP_LOST = "stop_lost"
    START_LOST = "start_lost"
    SPLICE_RELATED = "splice_related"
    INFRAME_INSERTION = "inframe_insertion"
    INFRAME_DELETION = "inframe_deletion"
    SYNONYMOUS = "synonymous"
    UNKNOWN = "unknown"


class Impact(str, Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    MODIFIER = "MODIFIER"


class AnnotationStatus(str, Enum):
    ANNOTATED = "ANNOTATED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class UnknownProviderError(ValueError):
    pass


class ProviderUnavailableError(RuntimeError):
    """Raised when a provider is registered but not usable in this environment."""


@dataclass
class ReferenceContext:
    reference_build: str | None
    transcript_source: str | None = None
    annotation_version: str | None = None


@dataclass
class ProviderMetadata:
    provider: str
    provider_version: str
    reference_build: str
    annotation_version: str
    transcript_source: str
    description: str = ""


@dataclass
class VariantInput:
    """Minimal, provider-agnostic variant representation."""

    key: str
    chromosome: str | None
    position: int | None
    reference: str | None
    alternate: str | None
    variant_type: str | None = None


@dataclass
class AnnotationRecord:
    key: str
    status: str
    consequence: str | None = None
    impact: str | None = None
    gene: str | None = None
    gene_id: str | None = None
    transcript: str | None = None
    transcript_id: str | None = None
    protein_change: str | None = None
    cds_position: int | None = None
    protein_position: int | None = None
    mutated_peptide: str | None = None
    failed_reason: str | None = None
    extra: dict = field(default_factory=dict)


class VariantAnnotator(ABC):
    """Base class for all annotation providers."""

    name: str = "base"

    def __init__(self, reference_build: str | None = None) -> None:
        self.reference_build = reference_build

    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        """Declare reference build, annotation version and transcript source."""

    @abstractmethod
    def annotate(
        self, variants: list[VariantInput], reference_context: ReferenceContext
    ) -> list[AnnotationRecord]:
        """Annotate a batch of variants."""

    def is_available(self) -> bool:
        """Whether the provider can run in the current environment."""
        return True
