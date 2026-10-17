"""Population HLA coverage estimate.

Given an individual's HLA alleles, estimates the fraction of a population that
would carry at least one of the design's restricting alleles, per locus and
overall (independent-locus approximation).

Frequency data: a small curated subset of common allele frequencies is embedded
for demonstration, and can be overridden/extended with a CSV
(``HLA_FREQUENCIES_CSV`` with columns ``allele,frequency``). For real design work
use a population-specific reference (e.g. AFND).
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.core.config import settings
from app.hla.normalization import normalize_hla_allele

CLASS_I_LOCI = ("A", "B", "C")
CLASS_II_LOCI = ("DRB1", "DQB1", "DPB1")

# Curated illustrative frequencies (global, approximate). Not population-specific.
_CURATED = {
    "HLA-A*02:01": 0.15, "HLA-A*01:01": 0.10, "HLA-A*03:01": 0.08,
    "HLA-A*11:01": 0.07, "HLA-A*24:02": 0.09, "HLA-A*26:01": 0.03,
    "HLA-A*32:01": 0.02,
    "HLA-B*07:02": 0.06, "HLA-B*08:01": 0.05, "HLA-B*35:01": 0.05,
    "HLA-B*15:01": 0.04, "HLA-B*40:01": 0.04, "HLA-B*44:02": 0.05,
    "HLA-C*07:02": 0.12, "HLA-C*04:01": 0.09, "HLA-C*05:01": 0.06,
    "HLA-C*06:02": 0.07, "HLA-C*03:03": 0.04,
    "HLA-DRB1*15:01": 0.06, "HLA-DRB1*03:01": 0.06, "HLA-DRB1*07:01": 0.06,
    "HLA-DQB1*06:02": 0.07, "HLA-DQB1*02:01": 0.10, "HLA-DPB1*04:01": 0.20,
}


def _frequency_files() -> list[str]:
    """Candidate frequency tables, highest priority first."""
    files: list[str] = []
    explicit = (settings.HLA_FREQUENCIES_CSV or "").strip()
    if explicit:
        files.append(explicit)
    # Real table shipped in the repository (derived from IEDB/AFND world data).
    repo_root = Path(__file__).resolve().parents[2]
    files.append(str(settings.storage_path / "hla_frequencies.csv"))
    files.append(str(repo_root / "storage" / "hla_frequencies.csv"))
    return files


def _load_file(path: str, table: dict[str, float]) -> bool:
    if not path or not Path(path).is_file():
        return False
    loaded = False
    try:
        with open(path) as handle:
            for row in csv.DictReader(handle):
                allele = (row.get("allele") or "").strip()
                norm = normalize_hla_allele(allele)
                if norm.valid and norm.normalized:
                    try:
                        table[norm.normalized] = float(row["frequency"])
                        loaded = True
                    except (TypeError, ValueError):
                        continue
    except Exception:  # noqa: BLE001
        return False
    return loaded


def _frequencies() -> dict[str, float]:
    table = dict(_CURATED)
    for path in _frequency_files():
        _load_file(path, table)
    return table


def status() -> dict:
    used = [p for p in _frequency_files() if Path(p).is_file()]
    return {
        "source": used[0] if used else "curated",
        "sources": used,
        "alleles": len(_frequencies()),
        "note": "World allele frequencies from IEDB/AFND where available; curated fallback otherwise.",
    }


def estimate(alleles: list[str]) -> dict:
    table = _frequencies()
    per_locus: dict[str, dict] = {}
    overall_miss = 1.0  # P(none of the design alleles is present)
    for locus in CLASS_I_LOCI + CLASS_II_LOCI:
        locus_alleles = []
        locus_miss = 1.0
        for raw in alleles:
            norm = normalize_hla_allele(raw)
            if not norm.valid or not norm.normalized or norm.locus != locus:
                continue
            freq = table.get(norm.normalized, 0.0)
            locus_alleles.append({"allele": norm.normalized, "frequency": freq})
            locus_miss *= 1.0 - freq
            overall_miss *= 1.0 - freq
        if not locus_alleles:
            continue
        per_locus[locus] = {
            "alleles": locus_alleles,
            "coverage": round(1.0 - locus_miss, 4),
        }
    return {
        "per_locus": per_locus,
        "overall_coverage": round(1.0 - overall_miss, 4),
        "loci_covered": sorted(per_locus.keys()),
        "note": "Union approximation over alleles; frequencies are illustrative (not population-specific). Use AFND and similar resources for production design.",
    }
