"""NetChop proteasomal-cleavage provider (processing chain).

NetChop 3.1 predicts per-position proteasomal cleavage probability — part of
the antigen-processing chain upstream of TAP transport and MHC binding.
Configure ``NETCHOP_DIR`` (a local NetChop installation containing the
``netchop`` binary); until then the provider reports UNAVAILABLE and is never
substituted by mock results.
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


def _netchop_dir() -> str:
    return (getattr(settings, "NETCHOP_DIR", "") or "").strip()


def _runner() -> str:
    explicit = (getattr(settings, "NETCHOP_RUNNER", "") or "").strip()
    if explicit:
        return explicit
    return str(
        Path(__file__).resolve().parents[2] / "scripts" / "netchop_runner.py"
    )


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


@register_prediction_provider
class NetChopProvider(PredictionProvider):
    provider_name = "netchop"
    provider_version = "3.1"
    is_mock = False
    description = (
        "NetChop 3.1 proteasomal-cleavage predictor (processing chain). "
        "Requires a local installation (NETCHOP_DIR with the netchop binary)."
    )

    def supported_hla(self) -> list[str]:
        return ["*"]

    def health_check(self) -> ProviderStatus:
        netchop_dir = _netchop_dir()
        if not netchop_dir:
            return ProviderStatus.UNAVAILABLE
        binary = Path(netchop_dir) / "netchop"
        if not (binary.is_file() and os.access(binary, os.X_OK)):
            return ProviderStatus.UNAVAILABLE
        if not Path(_runner()).is_file():
            return ProviderStatus.UNAVAILABLE
        return ProviderStatus.AVAILABLE

    def validate_input(self, inputs: list[PredictionInput]) -> ValidationResult:
        if not inputs:
            return ValidationResult(True)
        for item in inputs:
            if not item.peptide or not (7 <= len(item.peptide) <= 30):
                return ValidationResult(
                    False,
                    f"NetChop supports 7–30mer peptides (got {len(item.peptide or '')} for {item.candidate_id})",
                )
            if any(ch not in _STANDARD_AA for ch in item.peptide.upper()):
                return ValidationResult(False, f"Non-standard residue in {item.candidate_id}")
        return ValidationResult(True)

    def predict(self, inputs: list[PredictionInput]) -> list[PredictionOutput]:
        if self.health_check() != ProviderStatus.AVAILABLE:
            raise ProviderUnavailableError(
                "NetChop is not configured (NETCHOP_DIR with the netchop binary)."
            )
        rows = [
            item
            for item in inputs
            if item.peptide and 7 <= len(item.peptide) <= 30
        ]
        if not rows:
            return []

        requests = [
            {"key": item.candidate_id, "peptide": item.peptide.upper()}
            for item in rows
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump({"requests": requests}, handle)
            request_path = handle.name
        try:
            completed = subprocess.run(
                ["python3", _runner(), _netchop_dir(), request_path],
                capture_output=True,
                text=True,
                timeout=900,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderUnavailableError(f"NetChop timed out: {exc}") from exc
        finally:
            os.unlink(request_path)

        if completed.returncode != 0:
            raise ProviderUnavailableError(
                f"NetChop failed: {completed.stderr[-300:]}"
            )
        try:
            results = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderUnavailableError(f"NetChop produced invalid output: {exc}") from exc

        by_key = {item["key"]: item for item in results.get("results", [])}
        outputs: list[PredictionOutput] = []
        for item in rows:
            result = by_key.get(item.candidate_id)
            if result is None:
                continue
            try:
                value = float(result.get("cleavage"))
            except (TypeError, ValueError):
                value = None
            outputs.append(
                PredictionOutput(
                    candidate_id=item.candidate_id,
                    hla=item.hla_allele,
                    prediction_value=value,
                    metric_name="cleavage_score",
                    status=ProviderStatus.AVAILABLE.value,
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    input_hash=_hash(
                        self.provider_name, item.candidate_id, item.peptide or ""
                    ),
                )
            )
        return outputs
