#!/usr/bin/env python3
"""Download a processed 5' UTR MPRA dataset and normalise it for training.

Many public 5' UTR MPRAs (e.g. Sample et al. 2019, human 5' UTRs) publish a
per-sequence table of measured translation. Provide a direct URL to such a
processed CSV/TSV (optionally .gz) and this writes a ``sequence,value`` CSV
ready for ``scripts/train_utr_model.py``.

    MPRA_URL=https://.../5utr_mrl.csv.gz python scripts/download_mpra_utr.py

Note: the GEO series GSE114063 (Sample et al. 2019) only ships a 27 GB RAW
archive of BigWig tracks — there is no compact per-sequence table on GEO, so a
processed/mirrored CSV is required. Recognised columns: ``sequence``/``utr``/
``seq`` and ``value``/``mrl``/``rl``/``mean``.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import os
import sys
import urllib.request
from pathlib import Path

_SEQ_KEYS = ("sequence", "utr", "utr5", "seq", "5utr")
_VAL_KEYS = ("value", "mrl", "rl", "mean", "mean_rl", "log_rl")


def _open(path: Path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt")
    return open(path, "rt")


def normalise(src: Path, out: Path) -> int:
    rows = 0
    with _open(src) as handle:
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = "\t" if sample.count("\t") > sample.count(",") else ","
        reader = csv.DictReader(handle, delimiter=delimiter)
        cols = {c.strip().lower(): c for c in (reader.fieldnames or [])}
        seq_col = next((cols[k] for k in _SEQ_KEYS if k in cols), None)
        val_col = next((cols[k] for k in _VAL_KEYS if k in cols), None)
        if not seq_col or not val_col:
            print(f"could not find sequence/value columns in {reader.fieldnames}", file=sys.stderr)
            return 1
        with out.open("w", newline="") as sink:
            sink.write("sequence,value\n")
            for row in reader:
                seq = (row.get(seq_col) or "").strip().upper()
                value = (row.get(val_col) or "").strip()
                if not seq or not value:
                    continue
                try:
                    float(value)
                except ValueError:
                    continue
                sink.write(f"{seq},{value}\n")
                rows += 1
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("MPRA_URL", ""))
    parser.add_argument("--out", type=Path, default=Path("mpra_utr.csv"))
    args = parser.parse_args()

    if not args.url:
        print(
            "Set MPRA_URL to a processed per-sequence CSV/TSV (optionally .gz)\n"
            "with columns like sequence,value — e.g. a mirror of the Sample 2019\n"
            "human 5' UTR MPRA. GEO GSE114063 only provides a 27 GB BigWig RAW\n"
            "archive, so a processed table is required.\n\n"
            "  MPRA_URL=https://.../5utr_mrl.csv.gz python scripts/download_mpra_utr.py\n"
            "  python scripts/train_utr_model.py mpra_utr.csv",
            file=sys.stderr,
        )
        return 2

    raw = Path("mpra_utr_raw") / Path(args.url).name.split("?")[0]
    raw.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {args.url} ...")
    try:
        urllib.request.urlretrieve(args.url, raw)
    except Exception as exc:  # noqa: BLE001
        print(f"download failed: {exc}", file=sys.stderr)
        return 1
    rows = normalise(raw, args.out)
    if rows <= 0:
        print("no usable rows after normalisation", file=sys.stderr)
        return 3
    print(f"wrote {args.out} ({rows} rows)")
    print(f"train: python scripts/train_utr_model.py {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
