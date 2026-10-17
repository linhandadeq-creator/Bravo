#!/usr/bin/env python3
"""Download real MS immunopeptidome evidence from the IEDB query API.

Fetches MHC ligand records whose assay is mass-spectrometry based (8–11mers),
de-duplicates peptide–allele pairs and writes a bz2 CSV that the platform's
evidence service consumes (columns: allele, peptide, measurement_type,
measurement_source, measurement_value).

Usage:  python scripts/download_iedb_ms.py [max_rows] [output]
"""
from __future__ import annotations

import bz2
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "backend" / "storage" / "evidence" / "iedb_ms_ligands.csv.bz2"
API = "https://query-api.iedb.org/mhc_search"
STANDARD = set("ACDEFGHIKLMNPQRSTVWY")
PAGE = 1000


def fetch(params: dict) -> list[dict]:
    url = f"{API}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Bravo/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except Exception:  # noqa: BLE001
            time.sleep(1.5 * (attempt + 1))
    return []


def main() -> None:
    max_rows = int(sys.argv[1]) if len(sys.argv) > 1 else 400000
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)

    pairs: set[tuple[str, str]] = set()
    last_id = 0
    fetched = 0
    while len(pairs) < max_rows:
        query = {
            "select": "elution_id,linear_sequence,mhc_allele_name",
            "order": "elution_id.asc",
            "limit": PAGE,
            "elution_id": f"gt.{last_id}",
            "and": "(linear_sequence_length.gte.8,linear_sequence_length.lte.11,assay_names.ilike.*mass spectrometry*)",
        }
        rows = fetch(query)
        if not rows:
            break
        for row in rows:
            try:
                last_id = max(last_id, int(row["elution_id"]))
            except (KeyError, TypeError, ValueError):
                pass
            allele = (row.get("mhc_allele_name") or "").strip()
            peptide = (row.get("linear_sequence") or "").strip().upper()
            if not allele or not (8 <= len(peptide) <= 11):
                continue
            if any(ch not in STANDARD for ch in peptide):
                continue
            pairs.add((allele, peptide))
        fetched += len(rows)
        if fetched % 20000 == 0:
            print(f"  fetched {fetched} rows, {len(pairs)} unique pairs", flush=True)

    with bz2.open(out, "wt", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["allele", "peptide", "measurement_type", "measurement_source", "measurement_value"]
        )
        for allele, peptide in sorted(pairs):
            writer.writerow([allele, peptide, "mass spectrometry", "IEDB", ""])

    print(f"wrote {len(pairs)} unique peptide–allele pairs to {out}")


if __name__ == "__main__":
    main()
