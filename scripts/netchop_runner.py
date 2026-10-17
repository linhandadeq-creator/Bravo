#!/usr/bin/env python3
"""NetChop 3.1 proteasomal-cleavage runner (processing chain).

Usage:
    python scripts/netchop_runner.py <NETCHOP_DIR> <request.json>

Request JSON: {"requests": [{"key": "...", "peptide": "AAAAAAAAA"}]}
Output JSON:  {"results": [{"key": "...", "cleavage": 0.82}]}

``cleavage`` is the maximum per-position cleavage probability reported by
NetChop for the peptide.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_netchop(text: str) -> dict[str, float]:
    """Parse NetChop 3.1 output: blocks per peptide, columns pos/AA/C/score."""
    scores: dict[str, float] = {}
    current: str | None = None
    current_best = 0.0
    # NetChop prints a header per sequence then rows like:
    #   0  M   S  0.123
    row_re = re.compile(r"^\s*(\d+)\s+([A-Z])\s+\S+\s+([0-9.]+)")
    for line in text.splitlines():
        header = re.match(r"^\s*(?:----+)?\s*(\d+)\s+sequence\s+(\S+)", line)
        if header:
            if current is not None:
                scores[current] = current_best
            current = header.group(2)
            current_best = 0.0
            continue
        match = row_re.match(line)
        if match and current:
            current_best = max(current_best, float(match.group(3)))
    if current is not None:
        scores[current] = current_best
    return scores


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: netchop_runner.py <NETCHOP_DIR> <request.json>", file=sys.stderr)
        return 2
    netchop_dir = Path(sys.argv[1])
    request_path = Path(sys.argv[2])
    binary = netchop_dir / "netchop"
    if not binary.is_file():
        print(f"netchop binary missing: {binary}", file=sys.stderr)
        return 4

    payload = json.loads(request_path.read_text())
    requests = payload.get("requests", [])
    if not requests:
        print(json.dumps({"results": []}))
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        fasta = Path(tmp) / "peptides.fsa"
        with open(fasta, "w") as handle:
            for item in requests:
                handle.write(f">{item.get('key')}\n{item.get('peptide', '').upper()}\n")
        completed = subprocess.run(
            [str(binary), str(fasta)],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(netchop_dir),
        )
    if completed.returncode != 0:
        print(f"netchop failed: {completed.stderr[-300:]}", file=sys.stderr)
        return 5

    scores = parse_netchop(completed.stdout)
    results = [
        {"key": item.get("key"), "cleavage": scores.get(item.get("key"))}
        for item in requests
    ]
    print(json.dumps({"results": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
