"""Candidate ranking engine.

Computes a *Research Candidate Score* used only for ordering candidates. It is
explicitly **not** a clinical efficacy probability, a patient response
probability, or a vaccine effectiveness probability.
"""
from __future__ import annotations

from dataclasses import dataclass, field

RANKING_VERSION = "1.2.0"

DISCLAIMER = (
    "Research Candidate Score is a candidate ranking metric only. It is not a "
    "clinical efficacy probability, a patient response probability, or a vaccine "
    "effectiveness probability."
)

DEFAULT_WEIGHTS: dict[str, float] = {
    "presentation": 0.26,
    "expression": 0.13,
    "mutation": 0.13,
    "tumor_specificity": 0.17,
    "variant_quality": 0.08,
    "ms_evidence": 0.09,
    "clonality": 0.08,
    "agretopicity": 0.06,
}

WEIGHT_KEYS = tuple(DEFAULT_WEIGHTS.keys())

_SPECIFICITY_BY_CLASSIFICATION = {
    "TUMOR_ONLY": 1.0,
    "UNCERTAIN": 0.5,
    "SHARED": 0.0,
    "NORMAL_ONLY": 0.0,
}


@dataclass
class RankingInput:
    presentation: float | None = None
    expression: float | None = None
    expression_cap: float = 50.0
    mutation: float | None = None
    tumor_specificity: float = 0.0
    variant_quality: float | None = None
    quality_cap: float = 100.0
    ms_evidence: float = 0.0
    # Tumour variant allele frequency → clonality proxy (0.5 ≈ clonal het).
    clonality: float | None = None
    clonality_cap: float = 0.5
    # Agretopicity: (mutant − wild-type) predicted binding (higher = mutant
    # presented better than the self peptide).
    agretopicity: float | None = None
    agretopicity_cap: float = 0.5


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalize_presentation(value: float | None) -> float:
    return _clamp(value or 0.0)


def normalize_expression(value: float | None, cap: float) -> float:
    if value is None or cap <= 0:
        return 0.0
    return _clamp(value / cap)


def normalize_mutation(value: float | None) -> float:
    return _clamp(value or 0.0)


def normalize_quality(value: float | None, cap: float) -> float:
    if value is None or cap <= 0:
        return 0.0
    return _clamp(value / cap)


def normalize_specificity(value: float) -> float:
    return _clamp(value)


def normalize_clonality(value: float | None, cap: float = 0.5) -> float:
    """Map tumour allele frequency to a clonality proxy (0..1)."""
    if value is None or cap <= 0:
        return 0.0
    return _clamp(value / cap)


def normalize_agretopicity(value: float | None, cap: float = 0.5) -> float:
    """Map (mutant − wild-type) binding advantage to 0..1 (negative → 0)."""
    if value is None or cap <= 0:
        return 0.0
    return _clamp(value / cap)


def specificity_from_classification(classification: str | None) -> float:
    return _SPECIFICITY_BY_CLASSIFICATION.get((classification or "").upper(), 0.0)


def normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
    if not weights:
        return dict(DEFAULT_WEIGHTS)
    cleaned = {key: max(0.0, float(weights.get(key, DEFAULT_WEIGHTS[key]))) for key in WEIGHT_KEYS}
    total = sum(cleaned.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {key: value / total for key, value in cleaned.items()}


def compute_score(components: dict[str, float], weights: dict[str, float]) -> float:
    normalized = normalize_weights(weights)
    score = sum(normalized[key] * _clamp(components.get(key, 0.0)) for key in WEIGHT_KEYS)
    return round(score * 100, 2)


@dataclass
class RankingResult:
    score: float
    components: dict[str, float] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    version: str = RANKING_VERSION
    disclaimer: str = DISCLAIMER


class CandidateRankingEngine:
    def __init__(self, weights: dict[str, float] | None = None, version: str = RANKING_VERSION):
        self.weights = normalize_weights(weights)
        self.version = version

    def rank(self, data: RankingInput) -> RankingResult:
        components = {
            "presentation": normalize_presentation(data.presentation),
            "expression": normalize_expression(data.expression, data.expression_cap),
            "mutation": normalize_mutation(data.mutation),
            "tumor_specificity": normalize_specificity(data.tumor_specificity),
            "variant_quality": normalize_quality(data.variant_quality, data.quality_cap),
            "ms_evidence": _clamp(data.ms_evidence or 0.0),
            "clonality": normalize_clonality(data.clonality, data.clonality_cap),
            "agretopicity": normalize_agretopicity(
                data.agretopicity, data.agretopicity_cap
            ),
        }
        score = compute_score(components, self.weights)
        return RankingResult(
            score=score,
            components=components,
            weights=dict(self.weights),
            version=self.version,
        )
