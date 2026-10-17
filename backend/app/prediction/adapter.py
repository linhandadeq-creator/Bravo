"""Standard adapter for real prediction tools.

No specific tool is hardcoded into the platform. A validated research tool is
integrated by subclassing :class:`ExternalPredictionAdapter` and registering it;
until then the reserved ``external`` slot reports UNAVAILABLE so that mock
results are never silently substituted for real ones.
"""
from __future__ import annotations

from app.prediction.base import (
    PredictionInput,
    PredictionOutput,
    PredictionProvider,
    ProviderStatus,
    ProviderUnavailableError,
    ValidationResult,
)
from app.prediction.registry import register_prediction_provider


class ExternalPredictionAdapter(PredictionProvider):
    """Base class for integrating a validated external prediction tool."""

    is_mock = False
    provider_name = "external"
    provider_version = "unconfigured"
    description = "Reserved slot for a validated external prediction tool."

    def supported_hla(self) -> list[str]:
        return []

    def health_check(self) -> ProviderStatus:
        return ProviderStatus.UNAVAILABLE

    def validate_input(self, inputs: list[PredictionInput]) -> ValidationResult:
        return ValidationResult(
            False, "No external prediction provider is configured."
        )

    def predict(self, inputs: list[PredictionInput]) -> list[PredictionOutput]:
        raise ProviderUnavailableError(
            "No external prediction provider is configured; refusing to substitute "
            "a mock provider."
        )


@register_prediction_provider
class ReservedExternalProvider(ExternalPredictionAdapter):
    provider_name = "external"
    provider_version = "unconfigured"
