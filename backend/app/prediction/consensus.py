"""Consensus prediction provider.

Runs every available *real* predictor over the same inputs and combines their
results into a consensus value with an agreement score. This is the multi-
predictor ensemble layer: when only one predictor is installed it degrades to
that predictor (with a clear note); when a licensed NetMHCpan/NetMHCIIpan binary
is configured it participates automatically.

Each provider's values are converted to a within-batch percentile (higher =
better) so different score scales are comparable. Direction is declared per
provider; unknown providers default to "higher is better".
"""
from __future__ import annotations

import hashlib
import statistics

from app.prediction.base import (
    PredictionInput,
    PredictionOutput,
    PredictionProvider,
    ProviderStatus,
    ProviderUnavailableError,
    ValidationResult,
)
from app.prediction.registry import (
    get_prediction_provider,
    register_prediction_provider,
)

# Providers that participate in the consensus (excludes mock/panel/consensus).
# MixMHCpred adds an independent Class I binding signal; PRIME adds a
# TCR-facing immunogenicity signal — both fold into the ensemble when
# configured.
_MEMBERS = (
    "mhcflurry",
    "mhcnuggets",
    "mixmhcpred",
    "netmhcpan",
    "netmhciipan",
    "prime",
)

# Higher raw value is better for these; rank-style providers are inverted.
_HIGHER_IS_BETTER = {
    "mhcflurry": True,
    "mhcnuggets": True,
    "mixmhcpred": True,
    "netmhcpan": False,
    "netmhciipan": False,
    "prime": True,
}


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def percentile_rank(values: list[float], value: float, higher_better: bool) -> float:
    """Percentile (0..1, higher = better) of ``value`` within ``values``."""
    n = len(values)
    if n <= 1:
        base = 0.5
    else:
        below = sum(1 for v in values if v < value)
        equal = sum(1 for v in values if v == value)
        base = (below + 0.5 * (equal - 1)) / (n - 1)
    base = max(0.0, min(1.0, base))
    return base if higher_better else 1.0 - base


def aggregate(outputs: list[PredictionOutput]) -> list[PredictionOutput]:
    """Combine per-provider outputs into one consensus output per candidate."""
    by_provider: dict[str, list[PredictionOutput]] = {}
    for out in outputs:
        by_provider.setdefault(out.provider, []).append(out)

    # Pre-compute each provider's value list for percentile normalization.
    provider_values = {
        name: [o.prediction_value for o in outs if o.prediction_value is not None]
        for name, outs in by_provider.items()
    }

    per_candidate: dict[str, list[tuple[str, float, float]]] = {}
    candidate_hla: dict[str, str] = {}
    for name, outs in by_provider.items():
        values = provider_values[name]
        higher_better = _HIGHER_IS_BETTER.get(name, True)
        for out in outs:
            candidate_hla.setdefault(out.candidate_id, out.hla)
            if out.prediction_value is None:
                continue
            pct = percentile_rank(values, out.prediction_value, higher_better)
            per_candidate.setdefault(out.candidate_id, []).append(
                (name, out.prediction_value, pct)
            )

    results: list[PredictionOutput] = []
    for candidate_id, contributions in per_candidate.items():
        pcts = [c[2] for c in contributions]
        consensus = statistics.fmean(pcts) * 100 if pcts else None
        agreement = (
            max(0.0, 1.0 - statistics.pstdev(pcts)) if len(pcts) > 1 else 1.0
        )
        provider_detail = {
            name: {"value": value, "percentile": round(pct, 4)}
            for name, value, pct in contributions
        }
        confidence = (
            "high" if agreement >= 0.8 and len(pcts) >= 2
            else "single" if len(pcts) < 2
            else "low" if agreement < 0.5
            else "medium"
        )
        results.append(
            PredictionOutput(
                candidate_id=candidate_id,
                hla=candidate_hla.get(candidate_id, ""),
                prediction_value=consensus,
                metric_name="consensus_percentile",
                status=ProviderStatus.AVAILABLE.value,
                provider="consensus",
                provider_version="1.0.0",
                input_hash=_hash("consensus", candidate_id, str(len(pcts))),
                detail={
                    "providers": provider_detail,
                    "n_providers": len(pcts),
                    "agreement": round(agreement, 4),
                    "confidence": confidence,
                },
            )
        )
    return results


@register_prediction_provider
class ConsensusProvider(PredictionProvider):
    provider_name = "consensus"
    provider_version = "1.0.0"
    is_mock = False
    description = (
        "Multi-predictor consensus over all available real predictors "
        "(MHCflurry, MHCnuggets, MixMHCpred, PRIME immunogenicity, and "
        "NetMHCpan/NetMHCIIpan if configured)."
    )

    def __init__(self, reference_build: str | None = None) -> None:
        super().__init__(reference_build)
        self._members = [get_prediction_provider(name) for name in _MEMBERS]

    def supported_hla(self) -> list[str]:
        return ["*"]

    def health_check(self) -> ProviderStatus:
        if any(m.health_check() == ProviderStatus.AVAILABLE for m in self._members):
            return ProviderStatus.AVAILABLE
        return ProviderStatus.UNAVAILABLE

    def validate_input(self, inputs: list[PredictionInput]) -> ValidationResult:
        if not inputs:
            return ValidationResult(True)
        return ValidationResult(True)

    def predict(self, inputs: list[PredictionInput]) -> list[PredictionOutput]:
        available = [
            m for m in self._members if m.health_check() == ProviderStatus.AVAILABLE
        ]
        if not available:
            raise ProviderUnavailableError(
                "No real prediction provider is available for consensus."
            )
        collected: list[PredictionOutput] = []
        for member in available:
            try:
                if member.validate_input(inputs).ok:
                    collected.extend(member.predict(inputs))
            except ProviderUnavailableError:
                # A member dropping out must not fail the whole consensus.
                continue
        return aggregate(collected)
