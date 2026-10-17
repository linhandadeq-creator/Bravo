"""Chromosome naming normalisation.

VCF files in the wild mix ``chr1`` (UCSC) and ``1`` (Ensembl) styles. We
normalise to a canonical ``chr``-prefixed form for comparison and record when a
conversion happened, so the transformation is always auditable.
"""
from __future__ import annotations

from dataclasses import dataclass

CANONICAL_PREFIX = "chr"

_AUTOSOMES = {str(n) for n in range(1, 23)}
_SEX = {"X", "Y"}
_MITO = {"M", "MT"}

_KNOWN_BASES = _AUTOSOMES | _SEX | {"M"}


@dataclass(frozen=True)
class NormalizedChromosome:
    original: str
    normalized: str
    changed: bool
    known: bool


def _base(raw: str) -> str:
    value = raw.strip()
    if value[:3].lower() == "chr":
        value = value[3:]
    value = value.upper()
    if value == "MT":
        value = "M"
    elif value == "23":
        value = "X"
    elif value == "24":
        value = "Y"
    return value


def normalize_chromosome(raw: str | None) -> NormalizedChromosome:
    original = raw if raw is not None else ""
    base = _base(original)
    normalized = f"{CANONICAL_PREFIX}{base}" if base else ""
    changed = bool(base) and original != normalized
    known = base in _KNOWN_BASES
    return NormalizedChromosome(
        original=original,
        normalized=normalized,
        changed=changed,
        known=known,
    )
