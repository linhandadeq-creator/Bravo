"""Simulation-format registry: linear mRNA-LNP, circular RNA (PIE) and
self-amplifying RNA (saRNA).

The scaffold elements (IRES, PIE exon arms, replicase cassette, subgenomic
promoter) are *simulated* research placeholders: deterministic sequences with
realistic nucleotide composition that satisfy the platform's design
constraints (GC window, no homopolymers ≥ 6, no forbidden restriction sites,
no cryptic poly(A) signals). They are **not** functional biological elements
and every derived design is explicitly not for clinical or human use.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

FORMAT_MRNA_LNP = "mRNA-LNP"
FORMAT_CIRCRNA = "circRNA"
FORMAT_SARNA = "saRNA"

SUPPORTED_FORMATS: tuple[str, ...] = (FORMAT_MRNA_LNP, FORMAT_CIRCRNA, FORMAT_SARNA)

FIVE_UTR = "GGGAAACGCCACC"
THREE_UTR = "GCTGCCTGCTGGAGCCTGG"
START_CODON = "ATG"
STOP_CODON = "TGA"

FORBIDDEN_MOTIFS = ("AATAAA", "ATTAAA", "GTAAGT")
FORBIDDEN_RE = (
    "GAATTC", "GGATCC", "AAGCTT", "CTCGAG", "GCGGCCGC",
    "GTCGAC", "CTGCAG", "ACTAGT", "TCTAGA", "GGTACC", "GAGCTC",
    "GGTCTC", "CGTCTC", "GAAGAC", "CACCTGC",
)
MAX_HOMOPOLYMER = 5


def _violations(seq: str) -> int:
    hits = sum(1 for m in FORBIDDEN_MOTIFS if m in seq)
    hits += sum(1 for m in FORBIDDEN_RE if m in seq)
    run = 1
    best = 1
    for i in range(1, len(seq)):
        run = run + 1 if seq[i] == seq[i - 1] else 1
        best = max(best, run)
    if best > MAX_HOMOPOLYMER:
        hits += 1
    return hits


def _gc(seq: str) -> float:
    if not seq:
        return 0.0
    return 100.0 * sum(1 for ch in seq if ch in "GC") / len(seq)


def _window_gc_ok(seq: str, window: int = 30, low: float = 25.0, high: float = 75.0) -> bool:
    """All sampled 30-nt windows within the local GC bounds (matches the
    sequence-QC sampling cadence)."""
    for i in range(0, max(1, len(seq) - window + 1), 10):
        gc = _gc(seq[i : i + window])
        if gc < low or gc > high:
            return False
    return True


def _make_scaffold(length: int, seed: int, label: str) -> str:
    """Deterministic simulated scaffold with balanced GC (global and local
    windows) and no forbidden motifs (rejection sampling with a fixed seed —
    reproducible)."""
    rng = random.Random(seed)
    alphabet = ("A", "C", "G", "T")
    while True:
        seq = "".join(rng.choice(alphabet) for _ in range(length))
        if (
            _violations(seq) == 0
            and 35.0 <= _gc(seq) <= 65.0
            and _window_gc_ok(seq)
        ):
            return seq


# Simulated PIE (permuted intron-exon) homology arms — E1 is the 3' exon
# fragment, E2 the 5' exon fragment of a group-I intron PIE design.
PIE_E1 = _make_scaffold(66, seed=401, label="PIE_E1")
PIE_E2 = _make_scaffold(66, seed=402, label="PIE_E2")
# Simulated EMCV-like IRES (internal ribosome entry site placeholder).
IRES = _make_scaffold(240, seed=403, label="IRES")
# Simulated alphavirus replicase cassette (nsp1-4 placeholder, not functional).
REPLICASE = _make_scaffold(600, seed=404, label="REPLICASE")
# Simulated 26S subgenomic promoter ending in a Kozak context (GCCACC).
SGP = _make_scaffold(18, seed=405, label="SGP") + "GCCACC"


@dataclass(frozen=True)
class FormatSpec:
    key: str
    label: str
    description: str
    circular: bool
    cap: str | None
    poly_a: bool
    utr_optimizable: bool
    five_prime: tuple[tuple[str, str | None], ...]
    three_prime: tuple[tuple[str, str | None], ...]


FORMATS: dict[str, FormatSpec] = {
    FORMAT_MRNA_LNP: FormatSpec(
        key=FORMAT_MRNA_LNP,
        label="Linear mRNA (LNP)",
        description="Capped, polyadenylated linear mRNA delivered in lipid nanoparticles.",
        circular=False,
        cap="Cap1 (m7G + 2'-O-methylation)",
        poly_a=True,
        utr_optimizable=True,
        five_prime=(("5UTR", None), ("START", START_CODON)),
        three_prime=(("STOP", STOP_CODON), ("3UTR", THREE_UTR), ("POLYA", None)),
    ),
    FORMAT_CIRCRNA: FormatSpec(
        key=FORMAT_CIRCRNA,
        label="Circular RNA (PIE)",
        description="Circular mRNA via permuted intron-exon self-splicing; IRES-driven translation, no cap or poly(A).",
        circular=True,
        cap=None,
        poly_a=False,
        utr_optimizable=False,
        five_prime=(("PIE_E1", PIE_E1), ("IRES", IRES), ("START", START_CODON)),
        three_prime=(("STOP", STOP_CODON), ("PIE_E2", PIE_E2)),
    ),
    FORMAT_SARNA: FormatSpec(
        key=FORMAT_SARNA,
        label="Self-amplifying RNA (saRNA)",
        description="Replicase-driven self-amplifying RNA with a subgenomic promoter driving the antigen ORF.",
        circular=False,
        cap="Cap1 (m7G + 2'-O-methylation)",
        poly_a=True,
        utr_optimizable=True,
        five_prime=(
            ("5UTR", None),
            ("REPLICASE", REPLICASE),
            ("SGP", SGP),
            ("START", START_CODON),
        ),
        three_prime=(("STOP", STOP_CODON), ("3UTR", THREE_UTR), ("POLYA", None)),
    ),
}


def resolve_format(value: str | None) -> str:
    """Normalise/validate a simulation-format key; raises ValueError."""
    key = (value or "").strip()
    if key not in FORMATS:
        raise ValueError(
            f"Unsupported simulation_format '{value}'. "
            f"Supported: {', '.join(SUPPORTED_FORMATS)}."
        )
    return key
