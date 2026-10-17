#!/usr/bin/env python3
"""Convert a GEO/MPRA MRL table into the ``sequence,value`` training format.

Accepts tables with a 5' UTR sequence column (``utr``/``sequence``) and a mean
ribosome-load column (``rl``/``mrl``/``value``), e.g. GEO GSM4084997
(varying length 25–100 MRL). Optionally filters by a ``split`` column.

Usage:
    python scripts/prepare_mpra_training.py <input.csv[.gz]> <out.csv[.gz]> \
        [--split train|test|all] [--max-rows N]
"""
from __future__ import annotations

import argparse
import csv
import gzip
from pathlib import Path

SEQ_COLS = ("sequence", "utr", "seq", "5utr", "5_utr")
VAL_COLS = ("value", "rl", "mrl", "ribosome_load", "mean_ribosome_load")
STANDARD = set("ACGTU")


def open_text(path: Path, mode: str):
    if str(path).endswith(".gz"):
        return gzip.open(path, mode, newline="")
    return open(path, mode, newline="")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--split", default="all", choices=("train", "test", "all"))
    parser.add_argument("--max-rows", type=int, default=0)
    args = parser.parse_args()

    written = 0
    with open_text(args.input, "rt") as src:
        reader = csv.DictReader(src)
        cols = {c.lower(): c for c in (reader.fieldnames or [])}
        seq_col = next((cols[c] for c in SEQ_COLS if c in cols), None)
        val_col = next((cols[c] for c in VAL_COLS if c in cols), None)
        split_col = cols.get("split")
        if not seq_col or not val_col:
            raise SystemExit(
                f"need a sequence column {SEQ_COLS} and a value column {VAL_COLS}; "
                f"got {reader.fieldnames}"
            )
        with open_text(args.output, "wt") as dst:
            dst.write("sequence,value\n")
            for row in reader:
                if args.split != "all" and split_col:
                    if (row.get(split_col) or "").strip().lower() != args.split:
                        continue
                seq = (row.get(seq_col) or "").strip().upper().replace("U", "T")
                raw = (row.get(val_col) or "").strip()
                if not seq or not raw or any(ch not in STANDARD for ch in seq):
                    continue
                try:
                    value = float(raw)
                except ValueError:
                    continue
                dst.write(f"{seq},{value}\n")
                written += 1
                if args.max_rows and written >= args.max_rows:
                    break

    print(f"wrote {written} rows -> {args.output}")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
