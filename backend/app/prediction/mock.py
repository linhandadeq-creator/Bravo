"""Deterministic MOCK prediction provider.

This provider produces pseudo binding values for demos and automated tests. It
is explicitly marked as mock and must never be presented as a real scientific
prediction.
"""
from __future__ import annotations

import hashlib

from app.prediction.base import (
    PredictionInput,
    PredictionOutput,
    PredictionProvider,
    ProviderStatus,
    ValidationResult,
)
from app.prediction.registry import register_prediction_provider

METRIC_NAME = "mock_binding_score"


def _mock_value(peptide: str, hla: str) -> float:
    digest = hashlib.sha256(f"{peptide}|{hla}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


@register_prediction_provider
class MockPredictionProvider(PredictionProvider):
    provider_name = "mock"
    provider_version = "1.0.0"
    is_mock = True
    description = "Deterministic mock binding score for demos and tests. Not a real prediction."

    def supported_hla(self) -> list[str]:
        return ["*"]

    def health_check(self) -> ProviderStatus:
        return ProviderStatus.MOCK

    def validate_input(self, inputs: list[PredictionInput]) -> ValidationResult:
        for item in inputs:
            if not item.peptide:
                return ValidationResult(False, f"missing peptide for {item.candidate_id}")
            if not item.hla_allele:
                return ValidationResult(False, f"missing HLA for {item.candidate_id}")
        return ValidationResult(True)

    def predict(self, inputs: list[PredictionInput]) -> list[PredictionOutput]:
        outputs: list[PredictionOutput] = []
        for item in inputs:
            peptide = item.peptide or ""
            value = _mock_value(peptide, item.hla_allele)
            digest = hashlib.sha256(
                f"{self.provider_name}|{self.provider_version}|{item.candidate_id}|"
                f"{peptide}|{item.hla_allele}".encode()
            ).hexdigest()
            outputs.append(
                PredictionOutput(
                    candidate_id=item.candidate_id,
                    hla=item.hla_allele,
                    prediction_value=round(value, 4),
                    metric_name=METRIC_NAME,
                    status=ProviderStatus.MOCK.value,
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    input_hash=digest,
                    detail={"mock": True, "peptide": peptide},
                )
            )
        return outputs
