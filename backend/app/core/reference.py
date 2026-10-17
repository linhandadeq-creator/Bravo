"""Reference genome build handling.

Every analysis run must record an explicit reference build. Mixing builds
between the tumor and normal samples is a hard QC failure (never a silent
fallback).
"""
from __future__ import annotations

GRCH37 = "GRCh37"
GRCH38 = "GRCh38"

SUPPORTED_REFERENCE_BUILDS: tuple[str, ...] = (GRCH37, GRCH38)
DEFAULT_REFERENCE_BUILD = GRCH38

_ALIASES = {
    "GRCH37": GRCH37,
    "HG19": GRCH37,
    "B37": GRCH37,
    "GRCH38": GRCH38,
    "HG38": GRCH38,
    "B38": GRCH38,
}


def normalize_reference_build(value: str | None) -> str | None:
    """Return the canonical build name, or ``None`` when unrecognised/empty."""
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    return _ALIASES.get(candidate.upper())


def is_supported_reference_build(value: str | None) -> bool:
    return normalize_reference_build(value) in SUPPORTED_REFERENCE_BUILDS
