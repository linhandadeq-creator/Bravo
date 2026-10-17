#!/usr/bin/env python3
"""Benchmark the platform's prediction providers on a labelled peptide set.

Input CSV/TSV columns: peptide, hla, label (1 = binder/immunogenic, 0 = other).
Use a public dataset such as the IEDB weekly benchmark (binder vs random
decoys) or a curated immunogenicity set. For each available provider the
script reports AUROC so performance is measurable and reproducible.

Usage:
    python scripts/benchmark_predictors.py <dataset.tsv> [--providers mhcflurry,consensus]
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.prediction.benchmark import evaluate_provider  # noqa: E402
from app.prediction.registry import get_prediction_provider  # noqa: E402


def load(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, newline="") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        delimiter = "\t" if sample.count("\t") > sample.count(",") else ","
        for row in csv.DictReader(handle, delimiter=delimiter):
            peptide = (row.get("peptide") or row.get("Peptide") or "").strip()
            hla = (row.get("hla") or row.get("HLA") or row.get("allele") or "").strip()
            label = (row.get("label") or row.get("Label") or "").strip()
            if not peptide or label not in ("0", "1"):
                continue
            rows.append({"peptide": peptide, "hla": hla, "label": int(label)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--providers", default="mhcflurry,consensus,panel,mhcnuggets,mixmhcpred,prime")
    args = parser.parse_args()

    rows = load(args.dataset)
    if not rows:
        print("no valid rows (need peptide + label columns)", file=sys.stderr)
        return 1
    print(f"dataset: {args.dataset} · rows: {len(rows)} · positives: "
          f"{sum(1 for r in rows if r['label'] == 1)}")

    print(f"{'provider':<14}{'evaluated':>10}{'auc':>10}")
    for name in [n.strip() for n in args.providers.split(",") if n.strip()]:
        try:
            provider = get_prediction_provider(name)
        except ValueError as exc:
            print(f"{name:<14}{'':>10}{'':>10}  (unknown provider)")
            continue
        result = evaluate_provider(provider, rows)
        auc = f"{result.auc:.4f}" if result.auc is not None else "—"
        note = f"  ({result.note})" if result.note else ""
        if not result.available:
            note = f"  (unavailable: {result.note})"
        print(f"{result.provider:<14}{result.n_evaluated:>10}{auc:>10}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
