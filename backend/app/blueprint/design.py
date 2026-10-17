"""Constraint-based mRNA/DNA construct design engine.

Turns a set of epitope peptides into a manufacturing-oriented nucleic-acid
design under explicit constraints (GC window, homopolymer, restriction sites,
polyadenylation signals, CAI, direct repeats) using a seeded hill-climb with
restarts. Research design tool: unvalidated, not for clinical or human use.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.blueprint.formats import (
    FIVE_UTR,
    FORMAT_MRNA_LNP,
    FORMATS,
    THREE_UTR,
)

CODON_USAGE: dict[str, list[tuple[str, float]]] = {
    "A": [("GCC", 0.40), ("GCT", 0.26), ("GCA", 0.23), ("GCG", 0.11)],
    "R": [("AGA", 0.21), ("AGG", 0.21), ("CGG", 0.20), ("CGC", 0.19), ("CGA", 0.11), ("CGT", 0.08)],
    "N": [("AAC", 0.54), ("AAT", 0.46)],
    "D": [("GAC", 0.54), ("GAT", 0.46)],
    "C": [("TGC", 0.55), ("TGT", 0.45)],
    "Q": [("CAG", 0.73), ("CAA", 0.27)],
    "E": [("GAG", 0.58), ("GAA", 0.42)],
    "G": [("GGC", 0.34), ("GGA", 0.25), ("GGG", 0.25), ("GGT", 0.16)],
    "H": [("CAC", 0.59), ("CAT", 0.41)],
    "I": [("ATC", 0.48), ("ATT", 0.36), ("ATA", 0.16)],
    "L": [("CTG", 0.40), ("CTC", 0.20), ("TTG", 0.13), ("CTT", 0.13), ("TTA", 0.07), ("CTA", 0.07)],
    "K": [("AAG", 0.58), ("AAA", 0.42)],
    "M": [("ATG", 1.00)],
    "F": [("TTC", 0.55), ("TTT", 0.45)],
    "P": [("CCC", 0.33), ("CCT", 0.28), ("CCA", 0.27), ("CCG", 0.11)],
    "S": [("AGC", 0.24), ("TCC", 0.22), ("TCT", 0.15), ("TCA", 0.15), ("AGT", 0.15), ("TCG", 0.06)],
    "T": [("ACC", 0.36), ("ACA", 0.28), ("ACT", 0.24), ("ACG", 0.12)],
    "W": [("TGG", 1.00)],
    "Y": [("TAC", 0.57), ("TAT", 0.43)],
    "V": [("GTG", 0.47), ("GTC", 0.24), ("GTT", 0.18), ("GTA", 0.11)],
}

FORBIDDEN_RE_SITES = [
    "GAATTC", "GGATCC", "AAGCTT", "CTCGAG", "GCGGCCGC",
    "GTCGAC", "CTGCAG", "ACTAGT", "TCTAGA", "GGTACC", "GAGCTC",
    "GGTCTC", "CGTCTC", "GAAGAC", "CACCTGC",
]
FORBIDDEN_MOTIFS = ["AATAAA", "ATTAAA", "GTAAGT"]  # polyA signals + cryptic splice donor
_LINKER_PEPTIDE = "GGGGSGGGGS"
_RNA = str.maketrans("T", "U")

# Human tRNA adaptation weights (dos Reis et al. 2004, human tissue). Relative
# adaptiveness per codon; used for the tAI (tRNA adaptation index) objective.
TAI_TABLE: dict[str, float] = {
    "AAA": 0.85, "AAC": 0.96, "AAG": 0.85, "AAT": 0.71,
    "ACA": 0.56, "ACC": 0.96, "ACG": 0.31, "ACT": 0.71,
    "AGA": 0.45, "AGC": 0.68, "AGG": 0.45, "AGT": 0.50,
    "ATA": 0.19, "ATC": 0.97, "ATG": 1.00, "ATT": 0.81,
    "CAA": 0.48, "CAC": 0.85, "CAG": 1.00, "CAT": 0.64,
    "CCA": 0.66, "CCC": 0.89, "CCG": 0.31, "CCT": 0.75,
    "CGA": 0.18, "CGC": 0.62, "CGG": 0.41, "CGT": 0.30,
    "CTA": 0.20, "CTC": 0.70, "CTG": 1.00, "CTT": 0.55,
    "GAA": 0.91, "GAC": 0.80, "GAG": 1.00, "GAT": 0.73,
    "GCA": 0.64, "GCC": 1.00, "GCG": 0.38, "GCT": 0.79,
    "GGA": 0.62, "GGC": 0.89, "GGG": 0.59, "GGT": 0.48,
    "GTA": 0.19, "GTC": 0.73, "GTG": 1.00, "GTT": 0.50,
    "TAC": 0.90, "TAT": 0.68,
    "TCA": 0.52, "TCC": 0.86, "TCG": 0.21, "TCT": 0.69,
    "TGC": 0.87, "TGG": 1.00, "TGT": 0.62,
    "TTA": 0.20, "TTC": 0.94, "TTG": 0.55, "TTT": 0.66,
}

try:  # exact RNA folding (ViennaRNA); optional dependency
    import RNA as _vienna
except Exception:  # noqa: BLE001
    _vienna = None

_mfe_cache: dict[str, float] = {}


def mfe(seq: str) -> float | None:
    """Exact minimum free energy (kcal/mol) via ViennaRNA, or None."""
    if _vienna is None or not seq:
        return None
    rna = seq.upper().replace("T", "U")
    if rna in _mfe_cache:
        return _mfe_cache[rna]
    _, energy = _vienna.fold(rna)
    _mfe_cache[rna] = energy
    return energy


def structure_available() -> bool:
    return _vienna is not None


_AA_BY_CODON = {
    codon: aa for aa, options in CODON_USAGE.items() for codon, _ in options
}


@dataclass
class DesignConfig:
    format: str = FORMAT_MRNA_LNP
    five_utr: str = FIVE_UTR
    three_utr: str = THREE_UTR
    poly_a_length: int = 120
    max_homopolymer: int = 5
    gc_min: float = 30.0
    gc_max: float = 70.0
    gc_target_low: float = 40.0
    gc_target_high: float = 60.0
    max_direct_repeat: int = 12
    seeds: int = 16
    steps: int = 500
    # pick the best 5' UTR from the library using the translation model
    optimize_utr: bool = True
    # exact-structure refinement (ViennaRNA): bounded local search on the 5' end
    mfe_steps: int = 260
    mfe_window: int = 120
    # bounded whole-transcript structure refinement (kept small: full-sequence
    # folds are an order of magnitude slower than the 5' window)
    global_mfe_steps: int = 40
    # codon-level stability / codon-pair objectives (table-replaceable proxies)
    optimize_codon_stability: bool = True
    optimize_codon_pairs: bool = True


@dataclass
class Region:
    name: str
    type: str
    start: int
    end: int


@dataclass
class DesignedConstruct:
    dna: str
    rna: str
    regions: list[Region] = field(default_factory=list)
    gc_percent: float = 0.0
    cai: float = 0.0
    tai: float = 0.0
    expression_score: float = 0.0
    stability_score: float = 0.0
    u_content: float = 0.0
    innate_immune_score: float = 0.0
    innate_immune: dict | None = None
    three_utr_selection: dict | None = None
    codon_stability: float = 0.0
    codon_pair_score: float = 0.0
    codon_metrics_model: dict | None = None
    ivt_start: dict | None = None
    poly_a_design: dict | None = None
    constraints_ok: bool = False
    mfe: float | None = None
    mfe_per_nt: float | None = None
    format_key: str = FORMAT_MRNA_LNP
    circular: bool = False
    ligation_junction: int | None = None
    utr_selection: dict | None = None

    @property
    def length(self) -> int:
        return len(self.dna)


def _gc_percent(seq: str) -> float:
    if not seq:
        return 0.0
    return round(100.0 * sum(1 for ch in seq if ch in "GC") / len(seq), 2)


def _longest_homopolymer(seq: str) -> int:
    best = 1
    run = 1
    for i in range(1, len(seq)):
        run = run + 1 if seq[i] == seq[i - 1] else 1
        best = max(best, run)
    return best if seq else 0


def _has_long_repeat(seq: str, k: int) -> bool:
    seen: set[str] = set()
    for i in range(0, len(seq) - k + 1):
        kmer = seq[i : i + k]
        if kmer in seen:
            return True
        seen.add(kmer)
    return False


def _codon_to_aa(codon: str) -> str:
    return _AA_BY_CODON.get(codon, "X")


def _cai(codons: list[str]) -> float:
    weights = []
    for codon in codons:
        aa = _codon_to_aa(codon)
        if aa in ("M", "W"):
            continue
        options = CODON_USAGE.get(aa)
        if not options:
            continue
        max_freq = max(freq for _, freq in options)
        freq = next((f for c, f in options if c == codon), 0.0)
        if freq > 0:
            weights.append(freq / max_freq)
    if not weights:
        return 0.0
    product = 1.0
    for w in weights:
        product *= w
    return round(product ** (1.0 / len(weights)), 4)


_TAI_W_MAX: dict[str, float] = {
    aa: max(weight for codon, weight in TAI_TABLE.items() if _AA_BY_CODON.get(codon) == aa)
    for aa in CODON_USAGE
    if any(_AA_BY_CODON.get(codon) == aa for codon in TAI_TABLE)
}


def _tai(codons: list[str]) -> float:
    """tRNA adaptation index (geometric mean of per-codon adaptiveness)."""
    values = []
    for codon in codons:
        aa = _codon_to_aa(codon)
        w_max = _TAI_W_MAX.get(aa)
        if not w_max:
            continue
        weight = TAI_TABLE.get(codon, 0.0)
        if weight > 0 and w_max > 0:
            values.append(weight / w_max)
    if not values:
        return 0.0
    product = 1.0
    for value in values:
        product *= value
    return round(product ** (1.0 / len(values)), 4)


def _render(components: list[tuple[str, object]], skip_polya: bool = True) -> str:
    return "".join(
        value if isinstance(value, str) else "".join(value)
        for name, value in components
        if not (skip_polya and name == "POLYA")
    )


def _hard_violations(seq: str, config: DesignConfig) -> dict:
    re_hits = sum(1 for m in FORBIDDEN_RE_SITES if m in seq)
    poly_hits = sum(1 for m in FORBIDDEN_MOTIFS if m in seq)
    hp = max(0, _longest_homopolymer(seq) - config.max_homopolymer)
    repeat = 1 if _has_long_repeat(seq, config.max_direct_repeat) else 0
    return {"re": re_hits, "polya": poly_hits, "homopolymer": hp, "repeat": repeat}


def _window_gc_penalty(seq: str, window: int = 30, low: float = 25.0, high: float = 75.0) -> float:
    penalty = 0.0
    for i in range(0, max(1, len(seq) - window + 1), 10):
        gc = _gc_percent(seq[i : i + window])
        penalty += max(0.0, gc - high) + max(0.0, low - gc)
    return penalty


def _cost(components, config: DesignConfig, mutable_codons: list[str]) -> float:
    seq = _render(components)
    v = _hard_violations(seq, config)
    gc = _gc_percent(seq)
    gc_penalty = max(0.0, gc - config.gc_target_high) + max(
        0.0, config.gc_target_low - gc
    )
    cai = _cai(mutable_codons)
    tai = _tai(mutable_codons)
    cs = None
    cp = None
    if config.optimize_codon_stability or config.optimize_codon_pairs:
        try:
            from app.blueprint.codon_metrics import (
                codon_pair_score,
                codon_stability,
            )

            if config.optimize_codon_stability:
                cs = codon_stability(mutable_codons)
            if config.optimize_codon_pairs:
                cp = codon_pair_score(mutable_codons)
        except Exception:  # noqa: BLE001 - objectives degrade gracefully
            cs = None
            cp = None
    hard = v["re"] + v["polya"] + v["homopolymer"] + v["repeat"]
    window_penalty = _window_gc_penalty(seq)
    penalty = (
        hard * 1000.0
        + gc_penalty * 8.0
        + window_penalty * 4.0
        + (1.0 - cai) * 150.0
        + (1.0 - tai) * 60.0
    )
    if cs is not None:
        penalty += (1.0 - cs) * 25.0
    if cp is not None:
        penalty += (1.0 - cp) * 20.0
    return penalty


def _encode(peptide: str) -> list[str]:
    codons = []
    for aa in peptide.upper():
        opts = CODON_USAGE.get(aa)
        codons.append(opts[0][0] if opts else "NNN")
    return codons


def _encode_linker(index: int) -> list[str]:
    """Encode a linker with deterministic per-index codon variation.

    Identical linker cassettes create unavoidable ≥12 bp direct repeats when
    many antigens are concatenated; rotating synonyms per linker index breaks
    the repeats at the source (the hill-climb then refines around it).
    """
    rng = random.Random(4000 + index)
    codons = []
    for aa in _LINKER_PEPTIDE.upper():
        opts = CODON_USAGE.get(aa)
        if not opts:
            codons.append("NNN")
            continue
        codons.append(opts[rng.randrange(len(opts))][0])
    return codons


def _optimize(components, config: DesignConfig):
    positions = [
        (ci, k)
        for ci, (_name, value) in enumerate(components)
        if isinstance(value, list)
        for k in range(len(value))
    ]
    if not positions:
        return components

    def mutable_codons() -> list[str]:
        return [components[ci][1][k] for ci, k in positions]

    best_layout = None
    best_cost = None
    for seed in range(config.seeds):
        rng = random.Random(seed)
        for ci, k in positions:
            aa = _codon_to_aa(components[ci][1][k])
            choices = [c for c, _ in CODON_USAGE.get(aa, [])] or ["NNN"]
            components[ci][1][k] = choices[rng.randrange(min(len(choices), 3))]
        current = _cost(components, config, mutable_codons())
        # Simulated annealing: accept occasional worse moves early (temperature
        # decays) so the multi-objective landscape (CAI + tAI + GC + windows)
        # is searched globally instead of sticking in the first local minimum.
        temperature = max(1.0, current * 0.05)
        for step in range(config.steps):
            ci, k = positions[rng.randrange(len(positions))]
            aa = _codon_to_aa(components[ci][1][k])
            choices = [c for c, _ in CODON_USAGE.get(aa, [])]
            if len(choices) < 2:
                continue
            old = components[ci][1][k]
            alt = choices[rng.randrange(len(choices))]
            if alt == old:
                continue
            components[ci][1][k] = alt
            new = _cost(components, config, mutable_codons())
            delta = new - current
            if delta <= 0 or rng.random() < pow(2.718281828, -delta / max(temperature, 1e-9)):
                current = new
            else:
                components[ci][1][k] = old
            temperature *= 0.995
            if temperature < 0.01:
                temperature = 0.01
        if best_cost is None or current < best_cost:
            best_cost = current
            best_layout = [
                value[:] if isinstance(value, list) else value
                for _name, value in components
            ]
            if _hard_violations(_render(components), config) == {
                "re": 0,
                "polya": 0,
                "homopolymer": 0,
                "repeat": 0,
            } and config.gc_target_low <= _gc_percent(_render(components)) <= config.gc_target_high:
                break

    if best_layout is not None:
        for i, (name, _value) in enumerate(components):
            components[i] = (name, best_layout[i])

    # Greedy polish from the best layout (pure descent; the classic
    # hill-climb). Simulated annealing explores globally, then this pass
    # guarantees the feasibility repairs receive a locally-optimal start —
    # never worse than the old single-objective optimizer.
    if best_cost is not None and positions:
        rng = random.Random(999983)
        current = _cost(components, config, mutable_codons())
        for _ in range(config.steps):
            ci, k = positions[rng.randrange(len(positions))]
            aa = _codon_to_aa(components[ci][1][k])
            choices = [c for c, _ in CODON_USAGE.get(aa, [])]
            if len(choices) < 2:
                continue
            old = components[ci][1][k]
            alt = choices[rng.randrange(len(choices))]
            if alt == old:
                continue
            components[ci][1][k] = alt
            new = _cost(components, config, mutable_codons())
            if new <= current:
                current = new
            else:
                components[ci][1][k] = old
    return components


def _repair_windows(components, config: DesignConfig) -> None:
    """Deterministic repair: eliminate local GC-window violations.

    Runs after the hill-climb and the MFE refinement. For any sampled 30-nt
    window outside the hard bounds (25-75%), tries synonymous codons inside
    the window (low-GC choices when too hot, high-GC when too cold), accepting
    a swap only when it improves the window, breaks no hard constraint and
    keeps the CAI hard floor (0.65) satisfied. G/C-heavy real peptides can
    otherwise leave a single window slightly out of bounds.
    """
    window = 30
    low, high = 25.0, 75.0
    cai_floor = 0.65
    positions = [
        (ci, k)
        for ci, (_name, value) in enumerate(components)
        if isinstance(value, list)
        for k in range(len(value))
    ]
    if not positions:
        return
    offsets = _codon_offsets(components)

    def current_cai() -> float:
        return _cai([components[ci][1][k] for ci, k in positions])

    mutated = True
    iterations = 0
    while mutated and iterations < 500:
        mutated = False
        iterations += 1
        seq = _render(components)
        for start in range(0, max(1, len(seq) - window + 1), 10):
            gc = _gc_percent(seq[start : start + window])
            if low <= gc <= high:
                continue
            candidates = [
                (ci, k)
                for ci, k in positions
                if start <= offsets.get((ci, k), 10**9) < start + window
            ]
            want_lower = gc > high
            repaired = False
            for ci, k in candidates:
                aa = _codon_to_aa(components[ci][1][k])
                # Highest-frequency (best-CAI) synonyms first, so the repair
                # prefers codons that keep the CAI hard floor satisfied.
                choices = [c for c, _ in CODON_USAGE.get(aa, [])]
                if len(choices) < 2:
                    continue
                old = components[ci][1][k]
                for alt in choices:
                    if alt == old:
                        continue
                    components[ci][1][k] = alt
                    rendered = _render(components)
                    new_gc = _gc_percent(rendered[start : start + window])
                    within = low <= new_gc <= high
                    improved = (
                        (new_gc < gc) if want_lower else (new_gc > gc)
                    )
                    cai_ok = current_cai() >= cai_floor - 1e-9
                    if (within or improved) and cai_ok and not any(
                        _hard_violations(rendered, config).values()
                    ):
                        repaired = True
                        mutated = True
                        break
                    components[ci][1][k] = old
                if repaired:
                    break
            if repaired:
                break


def _restore_cai(components, config: DesignConfig) -> None:
    """Greedy CAI restoration within feasibility.

    After window repair, swaps codons back to higher-frequency synonyms
    wherever that keeps every hard constraint, the global GC targets and all
    sampled 30-nt windows in bounds. The hill-climb can get stuck below the
    CAI floor on G/C-heavy peptide sets; this pass recovers the floor without
    breaking manufacturability.
    """
    window = 30
    low, high = 25.0, 75.0
    positions = [
        (ci, k)
        for ci, (_name, value) in enumerate(components)
        if isinstance(value, list)
        for k in range(len(value))
    ]
    if not positions:
        return
    changed = True
    iterations = 0
    while changed and iterations < 2000:
        changed = False
        iterations += 1
        for ci, k in positions:
            aa = _codon_to_aa(components[ci][1][k])
            choices = [c for c, _ in CODON_USAGE.get(aa, [])]
            if len(choices) < 2:
                continue
            old = components[ci][1][k]
            old_index = choices.index(old) if old in choices else -1
            base_cai = _cai([components[c][1][k2] for c, k2 in positions])
            for alt in choices[: max(0, old_index)]:
                components[ci][1][k] = alt
                rendered = _render(components)
                if any(_hard_violations(rendered, config).values()):
                    components[ci][1][k] = old
                    continue
                if not (
                    config.gc_target_low
                    <= _gc_percent(rendered)
                    <= config.gc_target_high
                ):
                    components[ci][1][k] = old
                    continue
                new_cai = _cai([components[c][1][k2] for c, k2 in positions])
                if new_cai <= base_cai + 1e-9:
                    # Equal-frequency synonyms (e.g. TCT/TCA) must not
                    # oscillate; only strict CAI gains are kept.
                    components[ci][1][k] = old
                    continue
                ok = True
                for start in range(0, max(1, len(rendered) - window + 1), 10):
                    gc = _gc_percent(rendered[start : start + window])
                    if not (low <= gc <= high):
                        ok = False
                        break
                if ok:
                    changed = True
                    break
                components[ci][1][k] = old


def _repair_repeats(components, config: DesignConfig) -> None:
    """Deterministic repair of long direct repeats.

    Overlapping epitope windows from the same variant (e.g. ``HKRGKYIKTW`` /
    ``LHKRGKYIKTW``) share long identical peptide stretches whose preferred
    codons create ≥12 bp repeats; single-codon hill-climbing cannot cross the
    violating intermediates. This pass mutates synonyms inside one copy of a
    repeated k-mer, accepting only swaps that remove the repeat while keeping
    every hard constraint, the CAI floor and the GC-window bounds.
    """
    k = config.max_direct_repeat
    window = 30
    low, high = 25.0, 75.0
    cai_floor = 0.65
    positions = [
        (ci, kk)
        for ci, (_name, value) in enumerate(components)
        if isinstance(value, list)
        for kk in range(len(value))
    ]
    if not positions:
        return

    def count_repeats(seq: str) -> int:
        seen: set[str] = set()
        count = 0
        for i in range(0, len(seq) - k + 1):
            kmer = seq[i : i + k]
            if kmer in seen:
                count += 1
            else:
                seen.add(kmer)
        return count

    def windows_ok(seq: str) -> bool:
        for start in range(0, max(1, len(seq) - window + 1), 10):
            gc = _gc_percent(seq[start : start + window])
            if not (low <= gc <= high):
                return False
        return True

    def cai_ok() -> bool:
        return _cai([components[ci][1][kk] for ci, kk in positions]) >= cai_floor - 1e-9

    iterations = 0
    while iterations < 500:
        iterations += 1
        seq = _render(components)
        current_count = count_repeats(seq)
        if current_count == 0:
            return
        # Greedy descent: accept a swap that strictly reduces the repeat
        # count (intermediates may still contain repeats), keeping all other
        # hard constraints intact. The repeat constraint itself is the
        # descent objective, not a precondition.
        best: tuple[int, int, int, str] | None = None
        for ci, kk in positions:
            aa = _codon_to_aa(components[ci][1][kk])
            choices = [c for c, _ in CODON_USAGE.get(aa, [])]
            if len(choices) < 2:
                continue
            old = components[ci][1][kk]
            for alt in choices:
                if alt == old:
                    continue
                components[ci][1][kk] = alt
                rendered = _render(components)
                candidate_count = count_repeats(rendered)
                violations = _hard_violations(rendered, config)
                hard_ok = (
                    violations["re"] == 0
                    and violations["polya"] == 0
                    and violations["homopolymer"] == 0
                )
                windows = windows_ok(rendered)
                cai = cai_ok()
                components[ci][1][kk] = old
                if not (candidate_count < current_count) or not hard_ok or not windows or not cai:
                    continue
                if best is None or candidate_count < best[2]:
                    best = (ci, kk, candidate_count, alt)
        if best is None:
            return
        ci, kk, _count, alt = best
        components[ci][1][kk] = alt


def _repair_motifs(components, config: DesignConfig) -> None:
    """Remove immunostimulatory motifs (AUUUA, GUGUGU) in the coding region.

    A/rare ``I-Y`` dipeptide encodes ATT+TAT → AUUUA in the transcript, and
    ``V-V`` with GTG codons encodes GUGUGU. Swaps the offending codons to
    synonyms that break the motif, keeping every other constraint intact.
    """
    window = 30
    low, high = 25.0, 75.0
    cai_floor = 0.65
    positions = [
        (ci, kk)
        for ci, (_name, value) in enumerate(components)
        if isinstance(value, list)
        for kk in range(len(value))
    ]
    if not positions:
        return
    offsets = _codon_offsets(components)
    motifs = ("AUUUA", "GUGUGU")

    def coding() -> str:
        seq = _render(components)
        polya = next(
            (v for name, v in components if name == "POLYA"), ""
        )
        polya_len = len(polya) if isinstance(polya, str) else 0
        return (seq[: len(seq) - polya_len] if polya_len else seq).replace("T", "U")

    def feasible(seq: str) -> bool:
        violations = _hard_violations(seq, config)
        if violations["re"] or violations["polya"] or violations["homopolymer"] or violations["repeat"]:
            return False
        for start in range(0, max(1, len(seq) - window + 1), 10):
            gc = _gc_percent(seq[start : start + window])
            if not (low <= gc <= high):
                return False
        return True

    def cai_ok() -> bool:
        return _cai([components[ci][1][kk] for ci, kk in positions]) >= cai_floor - 1e-9

    iterations = 0
    while iterations < 300:
        iterations += 1
        rna = coding()
        offending = next((motif for motif in motifs if motif in rna), None)
        if offending is None:
            return
        idx = rna.index(offending)
        fixed = False
        for ci, kk in positions:
            start_pos = offsets.get((ci, kk), 10**9)
            if not (start_pos < idx + len(offending) and start_pos + 3 > idx):
                continue
            aa = _codon_to_aa(components[ci][1][kk])
            choices = [c for c, _ in CODON_USAGE.get(aa, [])]
            if len(choices) < 2:
                continue
            old = components[ci][1][kk]
            for alt in choices:
                if alt == old:
                    continue
                components[ci][1][kk] = alt
                dna = _render(components)
                if (
                    offending.replace("U", "T") not in dna.replace("T", "U")
                    and feasible(dna)
                    and cai_ok()
                ):
                    fixed = True
                    break
                components[ci][1][kk] = old
            if fixed:
                break


def _codon_offsets(components) -> dict[tuple[int, int], int]:
    offsets: dict[tuple[int, int], int] = {}
    cursor = 0
    for index, (_name, value) in enumerate(components):
        if isinstance(value, list):
            for k in range(len(value)):
                offsets[(index, k)] = cursor + k * 3
            cursor += len(value) * 3
        else:
            cursor += len(value)
    return offsets


def _refine_mfe(components, config: DesignConfig) -> None:
    """Bounded, structure-aware local search over the 5' region.

    Strongly structured 5' ends reduce translation; this nudges synonymous
    codons near the start to raise the (less negative) minimum free energy,
    without breaking hard constraints. Folding is cached, and the search is
    strictly bounded so the overall design stays fast.
    """
    if _vienna is None:
        return
    positions = [
        (ci, k)
        for ci, (_name, value) in enumerate(components)
        if isinstance(value, list)
        for k in range(len(value))
    ]
    if not positions:
        return
    offsets = _codon_offsets(components)
    rng = random.Random(20240101)
    window = config.mfe_window

    def window_seq() -> str:
        return _render(components)[:window]

    def feasible(seq: str) -> bool:
        if any(_hard_violations(seq, config).values()):
            return False
        for start in range(0, max(1, len(seq) - 30 + 1), 10):
            gc = _gc_percent(seq[start : start + 30])
            if not (25.0 <= gc <= 75.0):
                return False
        return True

    def cai_floor_ok() -> bool:
        codons = [components[ci][1][k] for ci, k in positions]
        return _cai(codons) >= 0.65 - 1e-9

    current = mfe(window_seq())
    if current is None:
        return
    for _ in range(config.mfe_steps):
        candidates = [
            (ci, k) for ci, k in positions if offsets.get((ci, k), 10**9) < window
        ]
        if not candidates:
            break
        ci, k = candidates[rng.randrange(len(candidates))]
        aa = _codon_to_aa(components[ci][1][k])
        choices = [c for c, _ in CODON_USAGE.get(aa, [])]
        if len(choices) < 2:
            continue
        old = components[ci][1][k]
        alt = choices[rng.randrange(len(choices))]
        if alt == old:
            continue
        components[ci][1][k] = alt
        rendered = _render(components)
        if not feasible(rendered) or not cai_floor_ok():
            components[ci][1][k] = old
            continue
        candidate = mfe(window_seq())
        if candidate is not None and candidate > current:
            current = candidate
        else:
            components[ci][1][k] = old


def _refine_structure_global(components, config: DesignConfig) -> None:
    """Global (whole-transcript) structure refinement.

    Beyond the 5' refinement, nudge synonymous codons anywhere in the ORF to
    raise the full-sequence MFE per nucleotide, keeping every hard constraint,
    the GC-window bounds and the CAI/tAI floors. Bounded (``mfe_steps`` folds)
    so the design stays fast; deterministic seed.
    """
    if _vienna is None:
        return
    positions = [
        (ci, k)
        for ci, (_name, value) in enumerate(components)
        if isinstance(value, list)
        for k in range(len(value))
    ]
    if not positions:
        return
    rng = random.Random(20250102)

    def coding() -> str:
        seq = _render(components)
        polya = next((v for name, v in components if name == "POLYA"), "")
        polya_len = len(polya) if isinstance(polya, str) else 0
        return seq[: len(seq) - polya_len] if polya_len else seq

    def feasible(seq: str) -> bool:
        if any(_hard_violations(seq, config).values()):
            return False
        for start in range(0, max(1, len(seq) - 30 + 1), 10):
            gc = _gc_percent(seq[start : start + 30])
            if not (25.0 <= gc <= 75.0):
                return False
        return True

    def floors_ok() -> bool:
        codons = [components[ci][1][k] for ci, k in positions]
        return _cai(codons) >= 0.65 - 1e-9 and _tai(codons) >= 0.2

    seq = coding()
    current = mfe(seq)
    if current is None:
        return
    for _ in range(config.global_mfe_steps):
        ci, k = positions[rng.randrange(len(positions))]
        aa = _codon_to_aa(components[ci][1][k])
        choices = [c for c, _ in CODON_USAGE.get(aa, [])]
        if len(choices) < 2:
            continue
        old = components[ci][1][k]
        alt = choices[rng.randrange(len(choices))]
        if alt == old:
            continue
        components[ci][1][k] = alt
        rendered = coding()
        if not feasible(rendered) or not floors_ok():
            components[ci][1][k] = old
            continue
        candidate = mfe(rendered)
        if candidate is not None and candidate > current:
            current = candidate
        else:
            components[ci][1][k] = old


def design_construct(
    peptides: list[str], config: DesignConfig | None = None
) -> DesignedConstruct:
    config = config or DesignConfig()
    peptides = [p for p in peptides if p]

    fmt = FORMATS.get(config.format, FORMATS[FORMAT_MRNA_LNP])
    circular = fmt.circular

    utr_selection: dict | None = None
    three_utr_selection: dict | None = None
    five_utr = config.five_utr
    three_utr = config.three_utr
    if fmt.utr_optimizable and config.optimize_utr:
        try:
            from app.blueprint.utr_model import best_utr, score as _utr_score
            from app.blueprint.stability import best_three_utr

            best = best_utr()
            five_utr = best
            utr_selection = {"sequence": best, **_utr_score(best)}
            three_utr, three_utr_selection = best_three_utr()
        except Exception:  # noqa: BLE001 - fall back to the configured UTR
            five_utr = config.five_utr

    components: list[tuple[str, object]] = []
    for name, value in fmt.five_prime:
        components.append((name, five_utr if (name == "5UTR" and value is None) else value))
    for index, peptide in enumerate(peptides):
        components.append((f"ANTIGEN_{index + 1:03d}", _encode(peptide)))
        if index < len(peptides) - 1:
            components.append((f"LINKER_{index + 1:03d}", _encode_linker(index)))
    for name, value in fmt.three_prime:
        if name == "3UTR" and value is None:
            components.append((name, three_utr))
        else:
            components.append(
                (name, "A" * config.poly_a_length if (name == "POLYA" and value is None) else value)
            )

    components = _optimize(components, config)
    _repair_windows(components, config)
    _restore_cai(components, config)
    _repair_repeats(components, config)
    _repair_motifs(components, config)
    _refine_structure_global(components, config)
    _refine_mfe(components, config)

    regions: list[Region] = []
    chunks: list[str] = []
    coding_codons: list[str] = []
    poly_a_length = 0
    cursor = 0
    for name, value in components:
        text = value if isinstance(value, str) else "".join(value)
        regions.append(Region(name, _region_type(name), cursor, cursor + len(text)))
        chunks.append(text)
        if not isinstance(value, str):
            coding_codons.extend(value)
        elif name == "START":
            coding_codons.append(value)
        if name == "POLYA":
            poly_a_length = len(text)
        cursor += len(text)

    dna = "".join(chunks)
    coding = dna[: len(dna) - poly_a_length]
    violations = _hard_violations(coding, config)
    tai = _tai(coding_codons)
    folding = mfe(coding)
    mfe_per_nt = round(folding / max(1, len(coding)), 4) if folding is not None else None
    rna_coding = coding.translate(_RNA)
    u_content = round(rna_coding.count("U") / max(1, len(rna_coding)), 4)
    stability_score = _stability_score(coding, poly_a_length)
    expression_score = _expression_score(
        cai=_cai(coding_codons),
        tai=tai,
        mfe_per_nt=mfe_per_nt,
        utr_score=(utr_selection or {}).get("utr_score"),
        stability=stability_score,
    )
    try:
        from app.blueprint.immunogenicity import innate_immune_score as _innate

        innate = _innate(coding, m1psi=True)
    except Exception:  # noqa: BLE001
        innate = None
    try:
        from app.blueprint.codon_metrics import (
            codon_pair_score as _pair_score,
            codon_stability as _stability,
            model_info as _codon_model_info,
        )

        codon_stability_value = _stability(coding_codons) or 0.0
        codon_pair_value = _pair_score(coding_codons) or 0.0
        codon_metrics_model = _codon_model_info()
    except Exception:  # noqa: BLE001
        codon_stability_value = 0.0
        codon_pair_value = 0.0
        codon_metrics_model = None
    return DesignedConstruct(
        dna=dna,
        rna=dna.translate(_RNA),
        regions=regions,
        gc_percent=_gc_percent(coding),
        cai=_cai(coding_codons),
        tai=tai,
        expression_score=expression_score,
        stability_score=stability_score,
        u_content=u_content,
        innate_immune_score=(innate or {}).get("score", 0.0),
        innate_immune=innate,
        three_utr_selection=three_utr_selection,
        codon_stability=codon_stability_value,
        codon_pair_score=codon_pair_value,
        codon_metrics_model=codon_metrics_model,
        ivt_start=ivt_start_score(dna),
        poly_a_design=poly_a_design(coding, poly_a_length),
        constraints_ok=not any(violations.values()),
        mfe=folding,
        mfe_per_nt=mfe_per_nt,
        format_key=fmt.key,
        circular=circular,
        ligation_junction=0 if circular else None,
        utr_selection=utr_selection,
    )


def ivt_start_score(dna: str) -> dict:
    """T7 in-vitro-transcription start check (transparent rule-based).

    T7 polymerase strongly prefers a G at the +1 transcribed position (and
    tolerates A); a pyrimidine +1 or a U at +2 lowers IVT yield. Returns a
    0..1 score plus notes; research heuristic, not a fitted model.
    """
    first = (dna[:1] or "").upper()
    second = (dna[1:2] or "").upper()
    score = {"G": 1.0, "A": 0.8, "C": 0.5, "T": 0.3}.get(first, 0.0)
    notes: list[str] = []
    if first != "G":
        notes.append("T7 prefers a G at the +1 position; consider a 5' UTR starting with G.")
    if second == "T":
        notes.append("Pyrimidine-rich +2 context can reduce T7 initiation.")
        score = max(0.0, score - 0.1)
    return {
        "model": "transparent_rule",
        "first_base": first,
        "score": round(score, 4),
        "t7_preferred_g": first == "G",
        "notes": notes,
    }


POLY_A_LENGTH_CANDIDATES: tuple[int, ...] = (60, 80, 100, 120, 150)


def poly_a_design(dna_coding: str, chosen_length: int) -> dict:
    """Evaluate poly(A) tail options with the transparent stability model.

    Longer tails increase stability up to the standard ~120 nt; segmented
    tails are flagged as an export-time option (not synthesised here).
    """
    variants = []
    for length in POLY_A_LENGTH_CANDIDATES:
        variants.append(
            {
                "length": length,
                "segmented": False,
                "stability_score": _stability_score(dna_coding, length),
            }
        )
    segmented = {
        "length": 120,
        "segmented": True,
        "segments": [40, 20, 40],
        "stability_score": _stability_score(dna_coding, 120),
        "note": "Segmented A40+spacer+A20+spacer+A40 is a documented design option; not synthesised here.",
    }
    best = max(variants, key=lambda item: (item["stability_score"], item["length"]))
    return {
        "model": "transparent_heuristic",
        "chosen": chosen_length,
        "recommended": best["length"],
        "variants": variants,
        "segmented_option": segmented,
    }


def _stability_score(dna_coding: str, poly_a_length: int) -> float:
    """Transparent mRNA-stability proxy (0..1): moderate AU richness in the
    transcript body plus a healthy poly(A) tail, penalised by ARE motifs.
    Documented heuristic — not a trained model."""
    rna = dna_coding.translate(_RNA)
    n = max(1, len(rna))
    au = (rna.count("A") + rna.count("U")) / n
    au_component = max(0.0, min(1.0, 1.0 - abs(au - 0.55) * 2.0))
    tail_component = min(1.0, poly_a_length / 120.0)
    are_penalty = max(0.0, 0.4 * (rna.count("AUUUA") + rna.count("UUAUUUAUU")))
    return round(max(0.0, min(1.0, 0.6 * au_component + 0.4 * tail_component - are_penalty)), 4)


def _expression_score(
    *,
    cai: float,
    tai: float,
    mfe_per_nt: float | None,
    utr_score: float | None,
    stability: float,
) -> float:
    """Composite predicted-expression score (0..100), fully documented:
    CAI (25) + tAI (15) + 5' structure openness (20) + 5'UTR model (20) +
    stability (20). Transparent heuristic — reproducible, not a trained model.
    """
    cai_part = 25.0 * max(0.0, min(1.0, (cai - 0.65) / 0.35))
    tai_part = 15.0 * max(0.0, min(1.0, tai))
    if mfe_per_nt is None:
        structure_part = 10.0
    else:
        structure_part = 20.0 * max(0.0, min(1.0, (mfe_per_nt + 0.5) / 0.5))
    utr_part = 20.0 * (utr_score if utr_score is not None else 0.5)
    stability_part = 20.0 * stability
    return round(cai_part + tai_part + structure_part + utr_part + stability_part, 1)


def _region_type(name: str) -> str:
    if name.startswith("ANTIGEN"):
        return "ANTIGEN"
    if name.startswith("LINKER"):
        return "LINKER"
    if name.startswith("PIE_"):
        return "PIE_EXON"
    return {
        "5UTR": "FIVE_PRIME_UTR",
        "START": "START_CODON",
        "STOP": "STOP_CODON",
        "3UTR": "THREE_PRIME_UTR",
        "POLYA": "POLY_A",
        "IRES": "IRES",
        "REPLICASE": "REPLICASE",
        "SGP": "SUBGENOMIC_PROMOTER",
    }.get(name, "OTHER")
