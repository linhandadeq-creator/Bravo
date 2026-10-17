"""MHCnuggets Class II provider (out-of-process).

MHCnuggets needs Keras 2 / TensorFlow 2.15, which conflicts with the main
environment. It therefore runs in an isolated venv via a runner subprocess. If
the isolated runtime (or Class II support) is missing, the provider reports
UNAVAILABLE and never falls back to the mock provider.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

from app.core.config import settings
from app.hla.normalization import normalize_hla_allele
from app.prediction.base import (
    PredictionInput,
    PredictionOutput,
    PredictionProvider,
    ProviderStatus,
    ProviderUnavailableError,
    ValidationResult,
)
from app.prediction.registry import register_prediction_provider

PROVIDER_VERSION = "2.4.1"
MODEL_NAME = "mhcnuggets_class2_BA"
_II_LOCI = {
    "DRA", "DRB1", "DRB3", "DRB4", "DRB5", "DQA1", "DQB1", "DPA1", "DPB1",
    "DMA", "DMB", "DOA", "DOB",
}


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _python() -> str:
    return settings.MHCNUGGETS_PYTHON or str(
        _backend_root() / ".venv-mhcii" / "bin" / "python"
    )


def _runner() -> str:
    return settings.MHCNUGGETS_RUNNER or str(
        _backend_root() / "scripts" / "mhcnuggets_runner.py"
    )


def _supported(allele: str | None) -> bool:
    if not allele:
        return False
    norm = normalize_hla_allele(allele)
    return bool(norm.valid and norm.allele_class == "II" and norm.normalized)


def _ic50_to_score(ic50: float | None) -> float | None:
    if ic50 is None or ic50 <= 0:
        return None
    return round(max(0.0, 1.0 - min(1.0, math.log10(ic50) / math.log10(50000.0))), 4)


@register_prediction_provider
class MHCNuggetsProvider(PredictionProvider):
    provider_name = "mhcnuggets"
    provider_version = PROVIDER_VERSION
    is_mock = False
    description = "MHCnuggets 2.4 — Class II binding (BA models, isolated runtime)."

    def supported_hla(self) -> list[str]:
        return ["HLA-DR*", "HLA-DQ*", "HLA-DP*"]

    def health_check(self) -> ProviderStatus:
        if os.path.exists(_python()) and os.path.exists(_runner()):
            return ProviderStatus.AVAILABLE
        return ProviderStatus.UNAVAILABLE

    def validate_input(self, inputs: list[PredictionInput]) -> ValidationResult:
        if not inputs:
            return ValidationResult(True)
        if not any(_supported(i.hla_allele) for i in inputs):
            return ValidationResult(
                False, "No Class II candidate is supported by MHCnuggets in this batch."
            )
        return ValidationResult(True)

    def predict(self, inputs: list[PredictionInput]) -> list[PredictionOutput]:
        if self.health_check() != ProviderStatus.AVAILABLE:
            raise ProviderUnavailableError(
                "MHCnuggets isolated runtime is not available (.venv-mhcii)."
            )

        rows = [
            item
            for item in inputs
            if _supported(item.hla_allele)
            and item.peptide
            and 8 <= len(item.peptide) <= 25
        ]
        if not rows:
            return []

        requests = [
            {
                "key": item.candidate_id,
                "peptide": item.peptide.upper(),
                "allele": (normalize_hla_allele(item.hla_allele).normalized or item.hla_allele),
            }
            for item in rows
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump({"requests": requests}, handle)
            request_path = handle.name

        env = dict(os.environ)
        env.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
        try:
            completed = subprocess.run(
                [_python(), _runner(), request_path],
                capture_output=True,
                text=True,
                timeout=900,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderUnavailableError(f"MHCnuggets timed out: {exc}") from exc
        finally:
            os.unlink(request_path)

        if completed.returncode != 0:
            raise ProviderUnavailableError(
                f"MHCnuggets failed: {completed.stderr[-300:]}"
            )
        try:
            results = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderUnavailableError(
                f"MHCnuggets produced invalid output: {exc}"
            ) from exc

        by_key = {item["key"]: item for item in results}
        outputs: list[PredictionOutput] = []
        for item in rows:
            result = by_key.get(item.candidate_id)
            if result is None:
                continue
            ic50 = None
            try:
                ic50 = float(result.get("ic50"))
            except (TypeError, ValueError):
                ic50 = None
            allele = normalize_hla_allele(item.hla_allele).normalized or item.hla_allele
            digest = hashlib.sha256(
                f"{self.provider_name}|{self.provider_version}|{item.candidate_id}|"
                f"{item.peptide}|{allele}".encode()
            ).hexdigest()
            outputs.append(
                PredictionOutput(
                    candidate_id=item.candidate_id,
                    hla=allele,
                    prediction_value=_ic50_to_score(ic50),
                    metric_name="mhcnuggets_ic50",
                    status=ProviderStatus.AVAILABLE.value,
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    input_hash=digest,
                    detail={
                        "allele": allele,
                        "peptide": item.peptide.upper(),
                        "binding_affinity": ic50,
                        "model": MODEL_NAME,
                        "model_version": self.provider_version,
                        "error": result.get("error"),
                    },
                )
            )
        return outputs
