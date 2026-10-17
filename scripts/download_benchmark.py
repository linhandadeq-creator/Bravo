#!/usr/bin/env python3
"""Download a public presentation benchmark and convert it to the harness format.

Uses the annotated benchmark released with the NetMHCpan papers (DTU Health
Tech): a binder/non-binder dataset of natural ligands vs decoys, standard for
reporting AUROC comparisons. Output columns: peptide, hla, label.

Usage:
    python scripts/download_benchmark.py [--url URL] [--out benchmark.tsv]
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

DEFAULT_URL = (
    "https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/data/Benchmark_annotated.xls"
)


def convert(xls_path: Path, out_path: Path) -> int:
    rows = 0
    try:
        import pandas as pd
    except ImportError:
        print(
            "pandas is required to convert the benchmark. "
            "pip install pandas openpyxl xlrd",
            file=sys.stderr,
        )
        return 1

    frame = pd.read_excel(xls_path)
    frame = frame.rename(columns=str.lower)
    peptide_col = next(
        (c for c in frame.columns if "peptide" in c), None
    )
    allele_col = next(
        (c for c in frame.columns if c in ("allele", "hla", "mhc")), None
    )
    binder_col = next(
        (c for c in frame.columns if "binder" in c or "label" in c), None
    )
    if not peptide_col or not binder_col:
        print(
            f"unexpected benchmark columns: {list(frame.columns)}",
            file=sys.stderr,
        )
        return 2

    with open(out_path, "w", newline="") as handle:
        handle.write("peptide\thla\tlabel\n")
        for _, row in frame.iterrows():
            peptide = str(row[peptide_col]).strip()
            label_raw = row[binder_col]
            try:
                label = 1 if float(label_raw) > 0 else 0
            except (TypeError, ValueError):
                continue
            if not peptide:
                continue
            allele = ""
            if allele_col and pd.notna(row[allele_col]):
                value = str(row[allele_col]).strip()
                allele = value if value.startswith("HLA-") else f"HLA-{value}"
            handle.write(f"{peptide}\t{allele}\t{label}\n")
            rows += 1
    return 0 if rows else 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument(
        "--source",
        choices=("netmhcpan", "iedb"),
        default="netmhcpan",
        help="netmhcpan: DTU annotated benchmark; iedb: IEDB weekly benchmark zip",
    )
    parser.add_argument("--out", type=Path, default=Path("benchmark_netmhcpan41.tsv"))
    args = parser.parse_args()

    if args.source == "iedb":
        import zipfile
        import io
        import csv as _csv

        url = (
            "https://datasets.iedb.org/database_other_v3.php"
            "?file_name=IEDB_weekly_benchmark.zip&file_format=zip"
        )
        print(f"downloading {url} ...")
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                data = response.read()
        except Exception as exc:  # noqa: BLE001
            print(f"download failed: {exc}", file=sys.stderr)
            return 1
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            name = next(
                (n for n in archive.namelist() if n.lower().endswith(".csv")),
                None,
            )
            if not name:
                print("no CSV inside the IEDB benchmark zip", file=sys.stderr)
                return 2
            text = archive.read(name).decode("utf-8", "replace")
        rows = 0
        with open(args.out, "w", newline="") as handle:
            handle.write("peptide\thla\tlabel\n")
            for row in _csv.DictReader(io.StringIO(text)):
                peptide = (row.get("peptide") or "").strip()
                label = (row.get("binder") or "").strip()
                if not peptide or label not in ("0", "1"):
                    continue
                allele = (row.get("allele") or "").strip()
                if allele and not allele.startswith("HLA-"):
                    allele = f"HLA-{allele}"
                handle.write(f"{peptide}\t{allele}\t{label}\n")
                rows += 1
        print(f"written {args.out} ({rows} rows)")
        print("run: python scripts/benchmark_predictors.py "
              f"{args.out} --providers mhcflurry,consensus,panel")
        return 0 if rows else 3

    print(f"downloading {args.url} ...")
    try:
        urllib.request.urlretrieve(args.url, "Benchmark_annotated.xls")
    except Exception as exc:  # noqa: BLE001
        print(f"download failed: {exc}", file=sys.stderr)
        print(
            "hint: if the DTU benchmark link is dead, try "
            "--source iedb (needs access to datasets.iedb.org).",
            file=sys.stderr,
        )
        return 1

    code = convert(Path("Benchmark_annotated.xls"), args.out)
    if code == 0:
        print(f"written {args.out}")
        print("run: python scripts/benchmark_predictors.py "
              f"{args.out} --providers mhcflurry,consensus,panel")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
