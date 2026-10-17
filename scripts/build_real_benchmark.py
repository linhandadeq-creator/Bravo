#!/usr/bin/env python3
"""Build a real presentation benchmark from local real data.

Positives: real IEDB mass-spectrometry MHC ligands (already shipped in
``backend/storage/evidence/iedb_ms_ligands.csv.bz2``). Negatives: shuffled
decoys of the positives (rejection-sampled to be unseen and non-self-
duplicating). Output columns: peptide, hla, label.

Deterministic (fixed seed), stratified by allele.

Usage:
    python scripts/build_real_benchmark.py [n_positives] [out.tsv]
"""
from __future__ import annotations

import bz2
import csv
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MS_LIGANDS = ROOT / "backend" / "storage" / "evidence" / "iedb_ms_ligands.csv.bz2"
ALLELE_RE = re.compile(r"^HLA-[ABC]\*\d{2,3}:\d{2,3}")
SEED = 20261016


def shuffle(peptide: str) -> str:
    chars = list(peptide)
    random.shuffle(chars)
    return "".join(chars)


def main() -> int:
    n_positives = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "benchmark_real.tsv"

    by_allele: dict[str, list[str]] = defaultdict(list)
    with bz2.open(MS_LIGANDS, "rt") as handle:
        for row in csv.DictReader(handle):
            allele = row["allele"].strip()
            if not ALLELE_RE.match(allele):
                continue
            peptide = row["peptide"].strip().upper()
            if not (8 <= len(peptide) <= 11):
                continue
            if not all(ch in "ACDEFGHIKLMNPQRSTVWY" for ch in peptide):
                continue
            by_allele[allele].append(peptide)

    alleles = sorted(by_allele)
    if not alleles:
        print("no concrete HLA-A/B/C MS ligands found", file=sys.stderr)
        return 1

    rng = random.Random(SEED)
    pool = [
        (allele, peptide)
        for allele in alleles
        for peptide in by_allele[allele]
    ]
    rng.shuffle(pool)

    per_allele = Counter()
    positives: list[tuple[str, str]] = []
    for allele, peptide in pool:
        if per_allele[allele] >= max(1, round(n_positives / len(alleles))):
            continue
        positives.append((allele, peptide))
        per_allele[allele] += 1
        if len(positives) >= n_positives:
            break

    positive_set = {peptide for _, peptide in positives}
    seen: set[str] = set()
    rows: list[tuple[str, str, int]] = []
    for allele, peptide in positives:
        rows.append((peptide, allele, 1))
        for _ in range(200):
            decoy = shuffle(peptide)
            if decoy == peptide or decoy in positive_set or decoy in seen:
                continue
            seen.add(decoy)
            break
        else:
            decoy = shuffle(peptide)
            while decoy == peptide:
                decoy = shuffle(peptide)
            seen.add(decoy)
        rows.append((decoy, allele, 0))

    rng.shuffle(rows)
    with open(out, "w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["peptide", "hla", "label"])
        writer.writerows(rows)

    print(f"written {out} ({len(rows)} rows; positives {len(positives)}, "
          f"negatives {len(rows) - len(positives)})")
    print("allele spread:", dict(sorted(per_allele.items())[:8]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
