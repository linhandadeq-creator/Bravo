"""Base class for external annotation providers that are not yet wired up.

A stub declares its intended metadata (so reference compatibility can be
reported) but is marked unavailable; calling :meth:`annotate` raises
:class:`ProviderUnavailableError` rather than silently returning UNKNOWN.
"""
from __future__ import annotations

from app.annotation.base import (
    AnnotationRecord,
    ProviderMetadata,
    ProviderUnavailableError,
    ReferenceContext,
    VariantAnnotator,
    VariantInput,
)


class ExternalProviderStub(VariantAnnotator):
    provider_version = "not-installed"
    display_name = "External provider"
    default_reference_build = "GRCh38"
    annotation_version = "unconfigured"
    transcript_source = "unconfigured"
    description = "Reserved provider. Runtime not configured."
    unavailable_reason = "Provider runtime is not installed in this environment."

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider=self.name,
            provider_version=self.provider_version,
            reference_build=self.reference_build or self.default_reference_build,
            annotation_version=self.annotation_version,
            transcript_source=self.transcript_source,
            description=self.description,
        )

    def is_available(self) -> bool:
        return False

    def annotate(
        self, variants: list[VariantInput], reference_context: ReferenceContext
    ) -> list[AnnotationRecord]:
        raise ProviderUnavailableError(self.unavailable_reason)
