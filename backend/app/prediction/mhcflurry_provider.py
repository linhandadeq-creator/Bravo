"""MHCflurry 2.3 Class I presentation predictor provider.

Real research provider. It predicts binding affinity, processing and presentation
for Class I alleles. If MHCflurry is unavailable or fails, it never falls back to
the mock provider — the engine records the failure / UNAVAILABLE explicitly.
"""
from __future__ import annotations

import hashlib
import os

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

_STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")
MODEL_NAME = "models_class1_presentation"
_MODEL = None  # cached Class1PresentationPredictor


def _package_version() -> str:
    try:
        from importlib.metadata import version

        return version("mhcflurry")
    except Exception:  # noqa: BLE001
        return "unavailable"


def _models_dir() -> str | None:
    try:
        import mhcflurry
        from mhcflurry.downloads import get_path

        path = get_path(MODEL_NAME)
    except Exception:  # noqa: BLE001
        return None
    if path and os.path.isdir(os.path.join(path, "models")):
        return path
    return None


def _supported(allele: str | None, peptide: str | None) -> tuple[bool, str, str]:
    if not allele or not peptide:
        return False, "", ""
    norm = normalize_hla_allele(allele)
    if not norm.valid or norm.allele_class != "I" or not norm.normalized:
        return False, "", ""
    pep = peptide.upper()
    if len(pep) < 8 or len(pep) > 11:
        return False, "", ""
    if any(ch not in _STANDARD_AA for ch in pep):
        return False, "", ""
    return True, norm.normalized, pep


def _enumerate_windows(context: str | None, offset: int | None) -> list[str]:
    """All 8-11mer windows of the mutant context that contain the mutation."""
    if not context:
        return []
    context = context.upper()
    length = len(context)
    seen: set[str] = set()
    windows: list[str] = []
    for size in range(8, min(11, length) + 1):
        for start in range(0, length - size + 1):
            if offset is not None and not (start <= offset < start + size):
                continue
            window = context[start : start + size]
            if window in seen:
                continue
            if all(ch in _STANDARD_AA for ch in window):
                seen.add(window)
                windows.append(window)
    if not windows and 8 <= length <= 11 and all(ch in _STANDARD_AA for ch in context):
        windows.append(context)
    return windows


def _load_model():
    global _MODEL
    if _MODEL is None:
        from mhcflurry import Class1PresentationPredictor

        _MODEL = Class1PresentationPredictor.load()
    return _MODEL


@register_prediction_provider
class MHCFlurryProvider(PredictionProvider):
    provider_name = "mhcflurry"
    provider_version = _package_version()
    is_mock = False
    description = "MHCflurry 2.3 — Class I presentation (binding + processing + presentation)."

    def supported_hla(self) -> list[str]:
        return ["HLA-A*", "HLA-B*", "HLA-C*"]

    def health_check(self) -> ProviderStatus:
        try:
            import importlib.util

            if importlib.util.find_spec("mhcflurry") is None:
                return ProviderStatus.UNAVAILABLE
        except Exception:  # noqa: BLE001
            return ProviderStatus.UNAVAILABLE
        if _models_dir() is None:
            return ProviderStatus.UNAVAILABLE
        return ProviderStatus.AVAILABLE

    def validate_input(self, inputs: list[PredictionInput]) -> ValidationResult:
        if not inputs:
            return ValidationResult(True)
        if not any(_supported(i.hla_allele, i.peptide)[0] for i in inputs):
            return ValidationResult(
                False,
                "No Class I candidate is supported by MHCflurry in this batch.",
            )
        return ValidationResult(True)

    def predict(self, inputs: list[PredictionInput]) -> list[PredictionOutput]:
        if self.health_check() != ProviderStatus.AVAILABLE:
            raise ProviderUnavailableError(
                "MHCflurry is not available (package or models missing)."
            )

        # Group by allele: the presentation predictor treats `alleles` as one
        # sample's allele set applied to all peptides, so predict per allele.
        groups: dict[str, list[tuple[PredictionInput, str]]] = {}
        for item in inputs:
            ok, allele, peptide = _supported(item.hla_allele, item.peptide)
            if ok:
                groups.setdefault(allele, []).append((item, peptide))
        if not groups:
            return []

        model = _load_model()
        model_path = _models_dir() or ""
        outputs: list[PredictionOutput] = []

        for allele, members in groups.items():
            # Enumerate 8-11mer epitope windows that contain the mutation.
            windows: list[tuple[int, str]] = []
            for index, (item, context) in enumerate(members):
                for peptide in _enumerate_windows(context, item.mutation_offset):
                    windows.append((index, peptide))
            if not windows:
                continue
            try:
                frame = model.predict(
                    peptides=[peptide for _, peptide in windows],
                    alleles=[allele],
                    include_affinity_percentile=True,
                    verbose=0,
                )
            except Exception as exc:  # noqa: BLE001 - surface as provider failure
                raise ProviderUnavailableError(
                    f"MHCflurry prediction failed: {exc}"
                ) from exc

            best: dict[int, tuple[float, object, str]] = {}
            for row_index, (member_index, peptide) in enumerate(windows):
                row = frame.iloc[row_index]
                score = _num(row.get("presentation_score"))
                if member_index not in best or (score or 0.0) > best[member_index][0]:
                    best[member_index] = (score or 0.0, row, peptide)

            for index, (item, _context) in enumerate(members):
                if index not in best:
                    continue
                _score, row, peptide = best[index]
                detail = {
                    "allele": allele,
                    "peptide": peptide,
                    "n_windows": len(
                        [w for i, w in windows if i == index]
                    ),
                    # MHCflurry returns the binding affinity (nM) column as "affinity"
                    "binding_affinity": _num(row.get("affinity")),
                    "binding_affinity_percentile": _num(row.get("affinity_percentile")),
                    "processing_score": _num(row.get("processing_score")),
                    "presentation_score": _num(row.get("presentation_score")),
                    "presentation_percentile": _num(row.get("presentation_percentile")),
                    "model": MODEL_NAME,
                    "model_version": self.provider_version,
                    "model_path": model_path,
                }
                digest = hashlib.sha256(
                    f"{self.provider_name}|{self.provider_version}|{item.candidate_id}|"
                    f"{peptide}|{allele}".encode()
                ).hexdigest()
                outputs.append(
                    PredictionOutput(
                        candidate_id=item.candidate_id,
                        hla=allele,
                        prediction_value=_num(row.get("presentation_score")),
                        metric_name="presentation_score",
                        status=ProviderStatus.AVAILABLE.value,
                        provider=self.provider_name,
                        provider_version=self.provider_version,
                        input_hash=digest,
                        detail=detail,
                    )
                )
        return outputs


def _num(value):
    try:
        import math

        number = float(value)
        if math.isnan(number):
            return None
        return round(number, 6)
    except (TypeError, ValueError):
        return None
