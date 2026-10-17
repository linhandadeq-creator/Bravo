"""Innate-immunity / dsRNA scoring for a designed transcript.

mRNA immunogenicity is driven by (a) dsRNA-like structure recognised by RIG-I /
MDA5 / PKR, (b) uridine-rich motifs sensed by TLR7/8 (strongly reduced by
N1-methylpseudouridine, m1Ψ), and (c) specific AU-rich / GU-rich motifs. This
module provides transparent, reproducible proxies — dsRNA is a structural
*fold-risk* estimate (longest self-complementary stem), not a trained dsRNA
model. Everything is labelled and never fabricated.
"""
from __future__ import annotations

_COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}
_M1PSI_URIDINE_SCALE = 0.35  # m1Ψ suppresses TLR7/8 uridine sensing


def longest_inverted_repeat(seq: str, max_loop: int = 40) -> int:
    """Length (bp) of the longest perfect self-complementary stem that could
    form a double-stranded (dsRNA-like) structure. Deterministic proxy."""
    text = seq.upper().replace("U", "T")
    n = len(text)
    best = 0
    for i in range(n):
        for loop in range(0, max_loop + 1):
            j = i + loop + 1
            if j >= n:
                break
            stem = 0
            while (
                i - stem >= 0
                and j + stem < n
                and text[i - stem] == _COMPLEMENT.get(text[j + stem], "")
            ):
                stem += 1
            if stem > best:
                best = stem
    return best


def dsrna_risk(seq: str) -> float:
    """0..1 dsRNA fold-risk proxy from the longest inverted-repeat stem."""
    stem = longest_inverted_repeat(seq)
    return round(min(1.0, stem / 15.0), 4)


def uridine_fraction(seq: str) -> float:
    rna = seq.upper().replace("T", "U")
    if not rna:
        return 0.0
    return round(rna.count("U") / len(rna), 4)


def cpg_count(seq: str) -> int:
    text = seq.upper().replace("U", "T")
    return sum(1 for i in range(len(text) - 1) if text[i : i + 2] == "CG")


def gu_rich_motifs(seq: str) -> int:
    rna = seq.upper().replace("T", "U")
    return rna.count("GUGUGU")


def au_rich_motifs(seq: str) -> int:
    rna = seq.upper().replace("T", "U")
    return rna.count("AUUUA")


def innate_immune_score(
    coding_dna: str, *, m1psi: bool = True, poly_a_excluded: int = 0
) -> dict:
    """Composite innate-immunity score (0..1, lower = less immunostimulatory).

    Documented, transparent heuristic (not a trained model):
      score = 0.50*uridine_eff + 0.25*dsrna_risk + 0.15*AUUUA + 0.10*CpG
    where ``uridine_eff`` scales the uridine fraction by 0.35 under m1Ψ
    modification (m1Ψ suppresses TLR7/8 activation).
    """
    coding = coding_dna[: len(coding_dna) - poly_a_excluded] if poly_a_excluded else coding_dna
    u = uridine_fraction(coding)
    u_eff = round(u * (_M1PSI_URIDINE_SCALE if m1psi else 1.0), 4)
    risk = dsrna_risk(coding)
    auuua = au_rich_motifs(coding)
    cpg = cpg_count(coding)
    score = (
        0.50 * min(1.0, u_eff / 0.35)
        + 0.25 * min(1.0, risk)
        + 0.15 * min(1.0, auuua / 3.0)
        + 0.10 * min(1.0, cpg / 10.0)
    )
    return {
        "score": round(min(1.0, score), 4),
        "m1psi": m1psi,
        "uridine": u,
        "uridine_effective": u_eff,
        "dsrna_risk": risk,
        "dsrna_stem": longest_inverted_repeat(coding),
        "auuua": auuua,
        "gugugu": gu_rich_motifs(coding),
        "cpg": cpg,
        "model": "transparent_heuristic",
    }
