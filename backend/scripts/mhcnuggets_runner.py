#!/usr/bin/env python3
"""Out-of-process MHCnuggets (Class II) runner.

Executed by the isolated Keras-2 venv. Reads a JSON request file and writes a
JSON result to stdout:

    request:  {"requests": [{"key": "...", "peptide": "...", "allele": "..."}]}
    result:   [{"key": "...", "peptide": "...", "allele": "...", "ic50": 123.4}]
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import sys
import tempfile
from collections import defaultdict

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import mhcnuggets  # noqa: E402

_BASE = os.path.dirname(mhcnuggets.__file__)


def main() -> int:
    request_path = sys.argv[1]
    with open(request_path) as handle:
        requests = json.load(handle).get("requests", [])

    groups: dict[str, list[dict]] = defaultdict(list)
    for item in requests:
        groups[item["allele"]].append(item)

    results: list[dict] = []
    os.chdir(_BASE)
    from mhcnuggets.src.predict import predict  # imported after chdir

    with tempfile.TemporaryDirectory() as workdir:
        for allele, items in groups.items():
            peptide_path = os.path.join(workdir, "peptides.txt")
            with open(peptide_path, "w") as handle:
                for item in items:
                    handle.write(f"{item['peptide']}\n")
            output_path = os.path.join(workdir, "out.csv")
            error = None
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    predict(
                        class_="II",
                        peptides_path=peptide_path,
                        mhc=allele,
                        output=output_path,
                    )
                except Exception as exc:  # noqa: BLE001
                    error = f"{type(exc).__name__}: {exc}"
            mapping: dict[str, str] = {}
            if os.path.exists(output_path):
                with open(output_path) as handle:
                    for row in csv.DictReader(handle):
                        mapping[row.get("peptide", "")] = (
                            row.get("ic50") or row.get("IC50") or ""
                        )
            for item in items:
                results.append(
                    {
                        "key": item["key"],
                        "peptide": item["peptide"],
                        "allele": allele,
                        "ic50": mapping.get(item["peptide"]),
                        "error": error,
                    }
                )

    json.dump(results, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
