"""PRIME 2.1 immunogenicity provider (TCR-facing, real research model).

PRIME (GfellerLab) predicts the immunogenicity of peptide–MHC-I complexes — a
complementary, TCR-facing signal beyond binding/presentation. Requires a local
PRIME 2.1 installation (``PRIME`` tool + ``lib/`` PerRank models) and the
MixMHCpred v3 tool; configure ``PRIME_DIR`` / ``PRIME_PYTHON``. Until then the
provider reports UNAVAILABLE and is never substituted by mock results.
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


def _prime_dir() -> str:
    return (getattr(settings, "PRIME_DIR", "") or "").strip()


def _python() -> str:
    return (getattr(settings, "PRIME_PYTHON", "") or "").strip() or "python3"


def _runner() -> str:
    explicit = (getattr(settings, "PRIME_RUNNER", "") or "").strip()
    if explicit:
        return explicit
    return str(
        Path(__file__).resolve().parents[3] / "scripts" / "prime_runner.py"
    )


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


@register_prediction_provider
class PrimeImmunogenicityProvider(PredictionProvider):
    provider_name = "prime"
    provider_version = "2.1"
    is_mock = False
    description = (
        "PRIME 2.1 immunogenicity predictor (TCR-facing, GfellerLab). "
        "Requires PRIME_DIR (PRIME tool + lib models) and MixMHCpred v3."
    )

    def supported_hla(self) -> list[str]:
        return ["HLA-A*", "HLA-B*", "HLA-C*"]

    def health_check(self) -> ProviderStatus:
        prime_dir = _prime_dir()
        if not prime_dir:
            return ProviderStatus.UNAVAILABLE
        if not (Path(prime_dir) / "PRIME").is_file():
            return ProviderStatus.UNAVAILABLE
        if not (Path(prime_dir) / "lib" / "run_PRIME.pl").is_file():
            return ProviderStatus.UNAVAILABLE
        if not Path(_runner()).is_file():
            return ProviderStatus.UNAVAILABLE
        return ProviderStatus.AVAILABLE

    def validate_input(self, inputs: list[PredictionInput]) -> ValidationResult:
        if not inputs:
            return ValidationResult(True)
        for item in inputs:
            if not item.peptide or not (8 <= len(item.peptide) <= 14):
                return ValidationResult(
                    False,
                    f"PRIME supports 8–14mer peptides (got {len(item.peptide or '')} for {item.candidate_id})",
                )
            if any(ch not in _STANDARD_AA for ch in item.peptide.upper()):
                return ValidationResult(False, f"Non-standard residue in {item.candidate_id}")
            if not item.hla_allele:
                return ValidationResult(False, f"Missing HLA allele for {item.candidate_id}")
        return ValidationResult(True)

    def predict(self, inputs: list[PredictionInput]) -> list[PredictionOutput]:
        if self.health_check() != ProviderStatus.AVAILABLE:
            raise ProviderUnavailableError(
                "PRIME is not configured (PRIME_DIR with trained models)."
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
                [_python(), _runner(), _prime_dir(), request_path],
                capture_output=True,
                text=True,
                timeout=1800,
                env={
                    **os.environ,
                    "MIXMHCPRED_TOOL": getattr(settings, "MIXMHCPRED_TOOL", "") or "",
                },
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderUnavailableError(f"PRIME timed out: {exc}") from exc
        finally:
            os.unlink(request_path)

        if completed.returncode != 0:
            raise ProviderUnavailableError(
                f"PRIME failed: {completed.stderr[-300:]}"
            )
        try:
            results = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderUnavailableError(f"PRIME produced invalid output: {exc}") from exc

        by_key = {item["key"]: item for item in results.get("results", [])}
        outputs: list[PredictionOutput] = []
        for item in rows:
            result = by_key.get(item.candidate_id)
            if result is None:
                continue
            try:
                value = float(result.get("immunogenicity"))
            except (TypeError, ValueError):
                value = None
            outputs.append(
                PredictionOutput(
                    candidate_id=item.candidate_id,
                    hla=item.hla_allele,
                    prediction_value=value,
                    metric_name="immunogenicity_score",
                    status=ProviderStatus.AVAILABLE.value,
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    input_hash=_hash(
                        self.provider_name, item.candidate_id, item.peptide or "", item.hla_allele or ""
                    ),
                )
            )
        return outputs
