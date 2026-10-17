"""Prediction benchmarking utilities (presentation / immunogenicity AUROC).

Evaluates the platform's providers against a labelled peptide–allele dataset
(e.g. the IEDB weekly benchmark, or curated immunogenicity sets), reporting
AUROC per provider so performance claims are measurable and reproducible.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.prediction.base import (
    PredictionInput,
    PredictionProvider,
    ProviderStatus,
    ProviderUnavailableError,
)


def roc_auc(labels: list[int], scores: list[float | None]) -> float | None:
    """Rank-based area under the ROC curve.

    ``labels`` ∈ {0, 1}; ``scores`` higher = more positive. Pairs without a
    score are dropped; returns None when both classes are absent.
    """
    pairs = [
        (label, score)
        for label, score in zip(labels, scores)
        if score is not None and label in (0, 1)
    ]
    positives = sum(1 for label, _ in pairs if label == 1)
    negatives = len(pairs) - positives
    if positives == 0 or negatives == 0:
        return None

    pairs.sort(key=lambda item: item[1])
    rank_sum = 0.0
    rank = 0
    i = 0
    n = len(pairs)
    while i < n:
        j = i
        while j < n and pairs[j][1] == pairs[i][1]:
            j += 1
        average = (i + 1 + j) / 2.0
        for k in range(i, j):
            if pairs[k][0] == 1:
                rank_sum += average
        i = j
    auc = (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)
    return round(max(0.0, min(1.0, auc)), 4)


@dataclass
class BenchmarkResult:
    provider: str
    metric: str
    n_evaluated: int
    auc: float | None
    available: bool = True
    note: str | None = None


def evaluate_provider(
    provider: PredictionProvider,
    rows: list[dict],
    n_workers: int = 1,
) -> BenchmarkResult:
    """Evaluate one provider on ``rows`` (``peptide``/``hla``/``label``)."""
    inputs = [
        PredictionInput(
            candidate_id=str(index),
            peptide=row["peptide"],
            peptide_representation=row["peptide"],
            hla_allele=row["hla"],
        )
        for index, row in enumerate(rows)
    ]
    if provider.health_check() not in (ProviderStatus.MOCK, ProviderStatus.AVAILABLE):
        return BenchmarkResult(
            provider=provider.provider_name,
            metric=provider.provider_name,
            n_evaluated=0,
            auc=None,
            available=False,
            note="provider unavailable",
        )
    validation = provider.validate_input(inputs)
    if not validation.ok:
        return BenchmarkResult(
            provider=provider.provider_name,
            metric=provider.provider_name,
            n_evaluated=0,
            auc=None,
            note=f"input rejected: {validation.reason}",
        )
    try:
        outputs = provider.predict(inputs)
    except ProviderUnavailableError as exc:
        return BenchmarkResult(
            provider=provider.provider_name,
            metric=provider.provider_name,
            n_evaluated=0,
            auc=None,
            available=False,
            note=str(exc),
        )
    by_candidate = {out.candidate_id: out for out in outputs}
    labels: list[int] = []
    scores: list[float | None] = []
    for index, row in enumerate(rows):
        out = by_candidate.get(str(index))
        labels.append(int(row["label"]))
        scores.append(out.prediction_value if out else None)
    auc = roc_auc(labels, scores)
    return BenchmarkResult(
        provider=provider.provider_name,
        metric=outputs[0].metric_name if outputs else provider.provider_name,
        n_evaluated=sum(1 for score in scores if score is not None),
        auc=auc,
    )
