"""MixMHCpred (v3) Class I binding provider (real research model).

MixMHCpred is a state-of-the-art public Class I binding predictor. The runner
drives the official GfellerLab ``MixMHCpred`` tool (``MIXMHCPRED_TOOL``, default
``backend/external/MixMHCpred``) with ``MIXMHCPRED_PYTHON`` (a Python with
numpy/pandas/scipy). Until configured, the provider reports UNAVAILABLE and is
never substituted by mock results.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from app.core.config import settings
from app.prediction.base import (
    PredictionInput,
    PredictionOutput,
    PredictionProvider,
    ProviderStatus,
    ProviderUnavailableError,
    ValidationResult,
)
from app.prediction.registry import register_prediction_provider

_STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")


def _python() -> str:
    return (getattr(settings, "MIXMHCPRED_PYTHON", "") or "").strip() or "python3"


def _runner() -> str:
    explicit = (getattr(settings, "MIXMHCPRED_RUNNER", "") or "").strip()
    if explicit:
        return explicit
    return str(
        Path(__file__).resolve().parents[3] / "scripts" / "mixmhcpred_runner.py"
    )


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


@register_prediction_provider
class MixMHCpredProvider(PredictionProvider):
    provider_name = "mixmhcpred"
    provider_version = "3.x"
    is_mock = False
    description = (
        "MixMHCpred v3 Class I binding predictor (official GfellerLab tool). "
        "Requires MIXMHCPRED_PYTHON; tool resolved from MIXMHCPRED_TOOL or "
        "backend/external/MixMHCpred."
    )

    def supported_hla(self) -> list[str]:
        return ["HLA-A*", "HLA-B*", "HLA-C*"]

    def health_check(self) -> ProviderStatus:
        if not Path(_runner()).is_file():
            return ProviderStatus.UNAVAILABLE
        return ProviderStatus.AVAILABLE if (getattr(settings, "MIXMHCPRED_PYTHON", "") or "").strip() else ProviderStatus.UNAVAILABLE

    def validate_input(self, inputs: list[PredictionInput]) -> ValidationResult:
        if not inputs:
            return ValidationResult(True)
        for item in inputs:
            if not item.peptide or not (8 <= len(item.peptide) <= 14):
                return ValidationResult(
                    False,
                    f"MixMHCpred supports 8–14mer peptides (got {len(item.peptide or '')} for {item.candidate_id})",
                )
            if any(ch not in _STANDARD_AA for ch in item.peptide.upper()):
                return ValidationResult(False, f"Non-standard residue in {item.candidate_id}")
            if not item.hla_allele:
                return ValidationResult(False, f"Missing HLA allele for {item.candidate_id}")
        return ValidationResult(True)

    def predict(self, inputs: list[PredictionInput]) -> list[PredictionOutput]:
        if self.health_check() != ProviderStatus.AVAILABLE:
            raise ProviderUnavailableError(
                "MixMHCpred is not configured (MIXMHCPRED_PYTHON)."
            )
        rows = [
            item
            for item in inputs
            if item.peptide and 8 <= len(item.peptide) <= 14
        ]
        if not rows:
            return []

        requests = [
            {
                "key": item.candidate_id,
                "peptide": item.peptide.upper(),
                "allele": item.hla_allele,
            }
            for item in rows
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump({"requests": requests}, handle)
            request_path = handle.name
        try:
            completed = subprocess.run(
                [_python(), _runner(), request_path],
                capture_output=True,
                text=True,
                timeout=1800,
                env={
                    **os.environ,
                    "MIXMHCPRED_TOOL": getattr(settings, "MIXMHCPRED_TOOL", "") or "",
                },
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderUnavailableError(f"MixMHCpred timed out: {exc}") from exc
        finally:
            os.unlink(request_path)

        if completed.returncode != 0:
            raise ProviderUnavailableError(
                f"MixMHCpred failed: {completed.stderr[-300:]}"
            )
        try:
            results = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderUnavailableError(f"MixMHCpred produced invalid output: {exc}") from exc

        by_key = {item["key"]: item for item in results.get("results", [])}
        outputs: list[PredictionOutput] = []
        for item in rows:
            result = by_key.get(item.candidate_id)
            if result is None:
                continue
            try:
                value = float(result.get("score"))
            except (TypeError, ValueError):
                value = None
            outputs.append(
                PredictionOutput(
                    candidate_id=item.candidate_id,
                    hla=item.hla_allele,
                    prediction_value=value,
                    metric_name="mixmhcpred_score",
                    status=ProviderStatus.AVAILABLE.value,
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    input_hash=_hash(
                        self.provider_name, item.candidate_id, item.peptide or "", item.hla_allele or ""
                    ),
                )
            )
        return outputs
