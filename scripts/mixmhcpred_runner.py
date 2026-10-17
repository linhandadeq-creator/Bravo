#!/usr/bin/env python3
"""MixMHCpred (v3.x) Class I binding runner.

Drives the official MixMHCpred bash tool (GfellerLab/MixMHCpred) in one batch
and parses its TSV output. The tool location is resolved from:

    1. env MIXMHCPRED_TOOL (explicit path to the ``MixMHCpred`` executable)
    2. <repo>/backend/external/MixMHCpred/MixMHCpred

The tool calls ``python3`` internally, so the interpreter running this script
(usually the platform venv) is prepended to PATH.

Usage:
    python scripts/mixmhcpred_runner.py <request.json>

Request JSON: {"requests": [{"key": "...", "peptide": "...", "allele": "HLA-A*02:01"}]}
Output JSON:  {"results": [{"key": "...", "score": 97.3}]}

Score = 100 - %Rank_bestAllele (higher = better predicted binder).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_ALLELE_RE = re.compile(r"^HLA-([ABC])\*(\d{2,3}):(\d{2,3})")


def _tool() -> str:
    explicit = os.environ.get("MIXMHCPRED_TOOL", "").strip()
    if explicit:
        return explicit
    return str(Path(__file__).resolve().parents[1] / "backend" / "external" / "MixMHCpred" / "MixMHCpred")


def _mix_name(allele: str) -> str | None:
    """HLA-A*02:01 -> A0201 (first four digits)."""
    match = _ALLELE_RE.match(allele.strip().upper())
    if not match:
        return None
    return f"{match.group(1)}{match.group(2)}{match.group(3)}"


def _supported_alleles(tool: str) -> set[str]:
    """Set of supported allele names from the tool's lib/alleles_list.txt."""
    alleles_file = Path(tool).resolve().parent / "lib" / "alleles_list.txt"
    if not alleles_file.is_file():
        return set()
    supported: set[str] = set()
    for line in alleles_file.read_text().splitlines():
        name = line.split("\t")[0].strip()
        if name and name != "Allele":
            supported.add(name)
    return supported


def _parse_output(text: str) -> dict[str, float]:
    """Map peptide -> 100 - %Rank_bestAllele from the MixMHCpred TSV."""
    scores: dict[str, float] = {}
    header: list[str] = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        if not header:
            header = [f.strip() for f in fields]
            continue
        row = dict(zip(header, fields))
        peptide = row.get("Peptide", "").strip()
        rank_raw = row.get("%Rank_bestAllele", "").strip()
        if not peptide or not rank_raw:
            continue
        try:
            scores[peptide] = 100.0 - float(rank_raw)
        except ValueError:
            continue
    return scores


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: mixmhcpred_runner.py <request.json>", file=sys.stderr)
        return 2
    request_path = Path(sys.argv[1])
    payload = json.loads(request_path.read_text())
    requests = payload.get("requests", [])
    if not requests:
        print(json.dumps({"results": []}))
        return 0

    tool = _tool()
    if not Path(tool).is_file():
        print(f"MixMHCpred tool not found: {tool}", file=sys.stderr)
        return 3

    supported = _supported_alleles(tool)

    peptides: list[str] = []
    allele_of: dict[str, str] = {}
    for item in requests:
        peptide = str(item.get("peptide", "")).upper()
        mix_name = _mix_name(str(item.get("allele", "")))
        if not peptide or mix_name is None:
            continue
        if supported and mix_name not in supported:
            continue
        peptides.append(peptide)
        allele_of[peptide] = mix_name

    if not peptides:
        print(json.dumps({"results": []}))
        return 0

    allele_list = sorted({name for name in allele_of.values()})
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False
    ) as pep_handle, tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False
    ) as out_handle:
        pep_handle.write("\n".join(peptides) + "\n")
        pep_path, out_path = pep_handle.name, out_handle.name

    env = dict(os.environ)
    # Prepend the invoking interpreter's bin dir (the platform venv, which
    # contains numpy/pandas/scipy) — do NOT resolve symlinks, since resolving
    # would point at the base interpreter outside the venv.
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")

    try:
        completed = subprocess.run(
            [tool, "-i", pep_path, "-a", ",".join(allele_list), "-o", out_path],
            capture_output=True,
            text=True,
            timeout=1800,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        print(f"MixMHCpred timed out: {exc}", file=sys.stderr)
        return 4
    finally:
        os.unlink(pep_path)

    if completed.returncode != 0 or not Path(out_path).is_file():
        detail = (completed.stderr or completed.stdout or "")[-300:]
        print(f"MixMHCpred failed: {detail}", file=sys.stderr)
        os.unlink(out_path)
        return 5

    try:
        scores = _parse_output(Path(out_path).read_text())
    finally:
        os.unlink(out_path)

    results = []
    for item in requests:
        peptide = str(item.get("peptide", "")).upper()
        results.append({"key": item.get("key"), "score": scores.get(peptide)})
    print(json.dumps({"results": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
