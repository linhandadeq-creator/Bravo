"""Sequence-level QC and in-silico release gate for a designed construct.

Computes manufacturability metrics and returns a PASS/FAIL release decision
(``PRODUCTION_READY`` / ``DESIGN_FAILED``). The poly(A) tail is excluded from
motif/homopolymer scans.
"""
from __future__ import annotations

import re

from dataclasses import dataclass, field

from app.blueprint.design import (
    FORBIDDEN_MOTIFS,
    FORBIDDEN_RE_SITES,
    DesignedConstruct,
    _gc_percent,
    _longest_homopolymer,
    mfe as exact_mfe,
)
from app.blueprint.formats import START_CODON

PASS = "PRODUCTION_READY"
FAIL = "DESIGN_FAILED"


@dataclass
class SequenceCheck:
    id: str
    label: str
    status: str
    detail: str


@dataclass
class SequenceQc:
    status: str
    manufacturability_score: float
    metrics: dict
    checks: list[SequenceCheck] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "manufacturability_score": self.manufacturability_score,
            "metrics": self.metrics,
            "checks": [
                {"id": c.id, "label": c.label, "status": c.status, "detail": c.detail}
                for c in self.checks
            ],
        }


_COMPLEMENT = {"A": "U", "U": "A", "G": "C", "C": "G", "T": "A"}


def _max_hairpin_stem(seq: str, min_loop: int = 3, max_loop: int = 30) -> int:
    """Longest local hairpin stem (bp) in an RNA sequence (approx.).

    Only local stem-loops (loop size 3–30 nt) are considered, which approximates
    real mRNA secondary structure better than global complementarity.
    """
    rna = seq.replace("T", "U")
    n = len(rna)
    best = 0
    for i in range(n):
        for loop in range(min_loop, max_loop + 1):
            j = i + loop
            if j >= n:
                break
            stem = 0
            while (
                i - stem >= 0
                and j + stem < n
                and rna[i - stem] == _COMPLEMENT.get(rna[j + stem], "")
            ):
                stem += 1
            if stem > best:
                best = stem
    return best


def _longest_direct_repeat(seq: str, min_k: int = 6, max_k: int = 20) -> int:
    best = 0
    n = len(seq)
    for k in range(min_k, max_k + 1):
        seen: set[str] = set()
        found = False
        for i in range(0, n - k + 1):
            kmer = seq[i : i + k]
            if kmer in seen:
                found = True
                break
            seen.add(kmer)
        if found:
            best = k
        else:
            break
    return best


def evaluate_sequence(designed: DesignedConstruct) -> SequenceQc:
    polya_len = next(
        (r.end - r.start for r in designed.regions if r.type == "POLY_A"), 0
    )
    coding = designed.dna[: len(designed.dna) - polya_len] if polya_len else designed.dna
    circular = bool(designed.circular)

    gc = _gc_percent(coding)
    homopolymer = _longest_homopolymer(coding)
    re_hits = sorted({m for m in FORBIDDEN_RE_SITES if m in coding})
    polya_signals = sorted({m for m in ("AATAAA", "ATTAAA") if m in coding})
    repeat = _longest_direct_repeat(coding)
    cai = designed.cai

    checks: list[SequenceCheck] = []

    def add(identifier: str, label: str, ok: bool, detail: str) -> None:
        checks.append(
            SequenceCheck(
                id=identifier, label=label, status="pass" if ok else "fail", detail=detail
            )
        )

    add("gc", "GC content", 30.0 <= gc <= 70.0, f"{gc}% (target 40-60%, hard bounds 30-70%)")
    add(
        "homopolymer",
        "Homopolymer",
        homopolymer <= 5,
        f"Longest homopolymer {homopolymer} (max 5)",
    )
    add(
        "restriction_sites",
        "Restriction sites",
        not re_hits,
        "None detected" if not re_hits else "Detected: " + ", ".join(re_hits),
    )
    add(
        "polya_signals",
        "Cryptic poly(A) signals",
        not polya_signals,
        "None detected" if not polya_signals else "Detected: " + ", ".join(polya_signals),
    )
    # sliding-window GC (local extremes)
    win = 30
    windows = [
        _gc_percent(coding[i : i + win])
        for i in range(0, max(1, len(coding) - win + 1), 10)
    ]
    gc_min_window = min(windows) if windows else gc
    gc_max_window = max(windows) if windows else gc
    add(
        "gc_window",
        "Local GC windows",
        25.0 <= gc_min_window and gc_max_window <= 75.0,
        f"Window (30nt) GC {gc_min_window}-{gc_max_window}% (bounds 25-75%)",
    )
    add(
        "length_limit",
        "Length limit",
        len(designed.dna) <= 4500,
        f"{len(designed.dna)} nt (max 4500)",
    )
    five_utr = next(
        (r for r in designed.regions if r.type == "FIVE_PRIME_UTR"), None
    )
    five_utr_seq = designed.dna[five_utr.start : five_utr.end] if five_utr else ""
    if circular:
        add(
            "five_utr_atg",
            "5'UTR free of upstream ATG",
            True,
            "No 5'UTR (circular RNA: IRES-driven initiation)",
        )
    else:
        add(
            "five_utr_atg",
            "5'UTR free of upstream ATG",
            "ATG" not in five_utr_seq,
            "No ATG in 5'UTR" if "ATG" not in five_utr_seq else "ATG present in 5'UTR",
        )
    add(
        "splice_donor",
        "Cryptic splice donor",
        "GTAAGT" not in coding,
        "None detected" if "GTAAGT" not in coding else "GTAAGT detected",
    )
    region = coding[:120] if len(coding) > 120 else coding
    exact = exact_mfe(region)
    stem = None
    mfe_per_nt = None
    if exact is not None:
        mfe_per_nt = round(exact / max(1, len(region)), 4)
        add(
            "secondary_structure",
            "RNA structure (MFE)",
            mfe_per_nt >= -0.30,
            f"5' MFE {exact} kcal/mol ({mfe_per_nt}/nt; floor -0.30)",
        )
    else:
        stem = _max_hairpin_stem(coding)
        add(
            "secondary_structure",
            "Secondary structure (approx.)",
            stem <= 8,
            f"Longest complementary stem {stem} bp (max 8)",
        )
    add("cai", "Codon adaptation (CAI)", cai >= 0.65, f"CAI={cai} (hard floor 0.65, target >=0.8)")
    add(
        "repeat",
        "Direct repeats",
        repeat < 12,
        f"Longest direct repeat {repeat} bp (max 12)",
    )
    add(
        "poly_a",
        "poly(A) tail",
        True,
        "Not applicable: circular RNA has no poly(A) tail",
    ) if circular else add(
        "poly_a",
        "poly(A) tail",
        polya_len >= 100,
        f"{polya_len} nt (min 100)",
    )

    # ---- Deeper sequence-science checks (release-relevant) ----
    start_region = next(
        (r for r in designed.regions if r.type == "START_CODON"), None
    )
    stop_region = next(
        (r for r in designed.regions if r.type == "STOP_CODON"), None
    )
    if start_region is not None and stop_region is not None:
        orf = designed.dna[start_region.start : stop_region.end]
    else:
        orf = coding
    starts_ok = orf.startswith(START_CODON)
    len_ok = len(orf) % 3 == 0
    body = orf[3:-3] if len(orf) >= 6 else ""
    no_internal_stop = not any(
        body[i : i + 3] in ("TAA", "TAG", "TGA")
        for i in range(0, max(0, len(body) - 2), 3)
    )
    ends_ok = orf.endswith(("TAA", "TAG", "TGA"))
    add(
        "orf_integrity",
        "ORF integrity",
        starts_ok and len_ok and no_internal_stop and ends_ok,
        f"start ATG={starts_ok}, length%3={len_ok}, no internal stop={no_internal_stop}, stop={ends_ok}",
    )

    kozak_ok = False
    if start_region is not None and not circular:
        ctx = designed.dna[max(0, start_region.start - 6) : start_region.start]
        kozak_ok = bool(re.match(r"^GCC[AG]CC$", ctx))
    if circular:
        add(
            "kozak",
            "Kozak context",
            True,
            "Not applicable: IRES-mediated initiation (simulated)",
        )
    else:
        add(
            "kozak",
            "Kozak context",
            kozak_ok,
            "GCCRCC present" if kozak_ok else "weak Kozak context",
        )

    rna = coding.replace("T", "U")
    are = rna.count("AUUUA")
    gu_rich = rna.count("GUGUGU")
    add(
        "immunostimulatory",
        "Immunostimulatory motifs",
        are <= 2 and gu_rich == 0,
        f"AUUUA={are} (max 2), GUGUGU={gu_rich}",
    )

    rare = {"CGA", "CGT", "CGG", "CTA", "ATA", "GTA", "TTA", "CCC", "ACG"}
    codons = [orf[i : i + 3] for i in range(0, max(0, len(orf) - 2), 3)]
    rare_frac = round(sum(1 for c in codons if c in rare) / len(codons), 3) if codons else 0.0
    add(
        "rare_codons",
        "Rare codon fraction",
        rare_frac <= 0.20,
        f"rare fraction {rare_frac} (max 0.20)",
    )

    passed = sum(1 for c in checks if c.status == "pass")
    score = round(100.0 * passed / len(checks), 1)
    status = PASS if passed == len(checks) else FAIL

    metrics = {
        "length": len(designed.dna),
        "coding_length": len(coding),
        "format": designed.format_key,
        "circular": circular,
        "gc_percent": gc,
        "tai": designed.tai,
        "u_content": designed.u_content,
        "expression_score": designed.expression_score,
        "stability_score": designed.stability_score,
        "innate_immune_score": designed.innate_immune_score,
        "dsrna_risk": (designed.innate_immune or {}).get("dsrna_risk"),
        "codon_stability": designed.codon_stability,
        "codon_pair_score": designed.codon_pair_score,
        "codon_metrics_model": designed.codon_metrics_model,
        "ivt_start": designed.ivt_start,
        "poly_a_design": designed.poly_a_design,
        "longest_homopolymer": homopolymer,
        "longest_direct_repeat": repeat,
        "cai": cai,
        "mfe": exact,
        "mfe_per_nt": mfe_per_nt,
        "max_hairpin_stem": stem,
        "gc_window_min": gc_min_window,
        "gc_window_max": gc_max_window,
        "poly_a_length": polya_len,
        "restriction_sites": re_hits,
        "polya_signals": polya_signals,
        "orf_start_ok": starts_ok,
        "orf_no_internal_stop": no_internal_stop,
        "kozak_ok": kozak_ok,
        "au_rich_motifs": are,
        "rare_codon_fraction": rare_frac,
        "forbidden_motifs_pool": list(FORBIDDEN_MOTIFS),
    }
    return SequenceQc(
        status=status, manufacturability_score=score, metrics=metrics, checks=checks
    )
