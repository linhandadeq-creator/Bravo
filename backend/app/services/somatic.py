"""Tumor/normal comparison producing :class:`SomaticCandidate` classifications.

A ``TUMOR_ONLY`` candidate is *not* asserted to be a true somatic mutation; it
is a candidate that requires orthogonal evidence. Confident ``SHARED`` calls
require the normal sample to carry the alternate allele with sufficient depth
and allele frequency, otherwise the candidate is ``UNCERTAIN``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.vcf_parser import ParsedVariant

TUMOR_ONLY = "TUMOR_ONLY"
NORMAL_ONLY = "NORMAL_ONLY"
SHARED = "SHARED"
UNCERTAIN = "UNCERTAIN"


@dataclass
class Candidate:
    chromosome: str
    position: int
    reference: str
    alternate: str
    classification: str
    tumor_allele_frequency: float | None
    normal_allele_frequency: float | None
    tumor_depth: int | None
    normal_depth: int | None
    tumor_genotype: str | None
    normal_genotype: str | None
    note: str


@dataclass
class SomaticResult:
    counts: dict[str, int] = field(default_factory=dict)
    candidates: list[Candidate] = field(default_factory=list)


def _has_alt_genotype(genotype: str | None) -> bool:
    if not genotype:
        return False
    return any(allele not in (".", "0") for allele in genotype.replace("|", "/").split("/"))


def _normal_evidence_confident(
    variant: ParsedVariant, min_depth: int, min_af: float
) -> bool:
    if variant.genotype is None and variant.allele_frequency is None and variant.depth is None:
        return False
    if not _has_alt_genotype(variant.genotype):
        return False
    if variant.depth is not None and variant.depth < min_depth:
        return False
    if variant.allele_frequency is not None and variant.allele_frequency < min_af:
        return False
    return True


def compare_variants(
    tumor_variants: list[ParsedVariant],
    normal_variants: list[ParsedVariant],
    min_depth: int,
    min_af: float,
) -> SomaticResult:
    tumor = {v.key: v for v in tumor_variants if v.is_valid and not v.is_duplicate and v.key}
    normal = {v.key: v for v in normal_variants if v.is_valid and not v.is_duplicate and v.key}

    counts = {TUMOR_ONLY: 0, NORMAL_ONLY: 0, SHARED: 0, UNCERTAIN: 0}
    candidates: list[Candidate] = []

    for key in sorted(set(tumor) | set(normal)):
        t = tumor.get(key)
        n = normal.get(key)
        if t is not None and n is None:
            classification = TUMOR_ONLY
            note = (
                "Present only in the tumor sample. Candidate only — not confirmed "
                "as a true somatic mutation without orthogonal evidence."
            )
        elif n is not None and t is None:
            classification = NORMAL_ONLY
            note = "Present only in the normal sample (likely germline)."
        elif t is not None and n is not None:
            if _normal_evidence_confident(n, min_depth, min_af):
                classification = SHARED
                note = "Present in both tumor and normal with confident normal evidence."
            else:
                classification = UNCERTAIN
                note = (
                    "Present in both samples but normal evidence is below the "
                    "confidence threshold (depth/allele frequency/genotype)."
                )
        else:  # pragma: no cover - union guarantees one is present
            continue

        counts[classification] += 1
        reference = t or n
        candidates.append(
            Candidate(
                chromosome=reference.chromosome_normalized or reference.chromosome or "",
                position=reference.position or 0,
                reference=(reference.reference or "").upper(),
                alternate=(reference.alternate or "").upper(),
                classification=classification,
                tumor_allele_frequency=t.allele_frequency if t else None,
                normal_allele_frequency=n.allele_frequency if n else None,
                tumor_depth=t.depth if t else None,
                normal_depth=n.depth if n else None,
                tumor_genotype=t.genotype if t else None,
                normal_genotype=n.genotype if n else None,
                note=note,
            )
        )

    return SomaticResult(counts=counts, candidates=candidates)
