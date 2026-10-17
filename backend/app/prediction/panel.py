"""Combined prediction panel: Class I (MHCflurry) + Class II (MHCnuggets).

Runs each real provider on the inputs it supports and merges the results, so a
single run yields both CD8 and CD4 candidate evidence. Never falls back to mock.
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
from app.prediction.mhcnuggets_provider import MHCNuggetsProvider
from app.prediction.mhcflurry_provider import MHCFlurryProvider
from app.prediction.registry import register_prediction_provider


@register_prediction_provider
class PanelProvider(PredictionProvider):
    provider_name = "panel"
    provider_version = "1.0.0"
    is_mock = False
    description = "Combined panel: MHCflurry (Class I) + MHCnuggets (Class II)."

    def __init__(self, reference_build: str | None = None) -> None:
        super().__init__(reference_build)
        self._class1 = MHCFlurryProvider(reference_build)
        self._class2 = MHCNuggetsProvider(reference_build)

    def supported_hla(self) -> list[str]:
        return ["*"]

    def health_check(self) -> ProviderStatus:
        if self._class1.health_check() == ProviderStatus.AVAILABLE:
            return ProviderStatus.AVAILABLE
        if self._class2.health_check() == ProviderStatus.AVAILABLE:
            return ProviderStatus.AVAILABLE
        return ProviderStatus.UNAVAILABLE

    def validate_input(self, inputs: list[PredictionInput]) -> ValidationResult:
        if not inputs:
            return ValidationResult(True)
        return ValidationResult(True)

    def predict(self, inputs: list[PredictionInput]) -> list[PredictionOutput]:
        if self.health_check() != ProviderStatus.AVAILABLE:
            raise ProviderUnavailableError(
                "Neither Class I (MHCflurry) nor Class II (MHCnuggets) runtime is available."
            )
        outputs: list[PredictionOutput] = []
        if self._class1.health_check() == ProviderStatus.AVAILABLE:
            outputs.extend(self._class1.predict(inputs))
        if self._class2.health_check() == ProviderStatus.AVAILABLE:
            outputs.extend(self._class2.predict(inputs))
        return outputs
