#!/usr/bin/env python3
"""PRIME 2.1 immunogenicity runner (GfellerLab/PRIME).

Drives the official PRIME 2.1 tool (bash wrapper + native binary + PerRank
models) over a JSON batch. PRIME 2.1 requires the MixMHCpred v3 tool, resolved
from env ``MIXMHCPRED_TOOL`` (default ``backend/external/MixMHCpred``).

Usage:
    python scripts/prime_runner.py <PRIME_DIR> <request.json>

Request JSON: {"requests": [{"key": "...", "peptide": "...", "allele": "HLA-A*02:01"}]}
Output JSON:  {"results": [{"key": "...", "immunogenicity": 0.272}]}

immunogenicity = PRIME Score_bestAllele (higher = more immunogenic).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _default_mix() -> str:
    return str(
        Path(__file__).resolve().parents[1]
        / "backend"
        / "external"
        / "MixMHCpred"
        / "MixMHCpred"
    )


def _prime_name(allele: str) -> str | None:
    """Mirror PRIME's own normalization: HLA-A*02:01 -> A0201."""
    name = allele.strip().upper()
    if name.startswith("HLA-"):
        name = name[4:]
    name = name.replace("*", "")
    if len(name) == 6 and name[3] == ":":
        name = name[:3] + name[4:]
    return name if name else None


def _supported_alleles(prime_dir: Path) -> set[str]:
    """Source column of PRIME's lib/alleles_mapping.txt."""
    mapping = prime_dir / "lib" / "alleles_mapping.txt"
    if not mapping.is_file():
        return set()
    supported: set[str] = set()
    for line in mapping.read_text().splitlines():
        if line.strip():
            supported.add(line.split("\t")[0].strip())
    return supported


def _parse_output(text: str) -> dict[str, float]:
    """Map peptide -> Score_bestAllele from the PRIME TSV."""
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
        score_raw = row.get("Score_bestAllele", "").strip()
        if not peptide or not score_raw:
            continue
        try:
            scores[peptide] = float(score_raw)
        except ValueError:
            continue
    return scores


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: prime_runner.py <PRIME_DIR> <request.json>", file=sys.stderr)
        return 2
    prime_dir = Path(sys.argv[1]).resolve()
    request_path = Path(sys.argv[2])

    tool = prime_dir / "PRIME"
    if not tool.is_file():
        print(f"PRIME tool not found: {tool}", file=sys.stderr)
        return 3
    mix = os.environ.get("MIXMHCPRED_TOOL", "").strip() or _default_mix()
    if not Path(mix).is_file():
        print(f"MixMHCpred tool not found: {mix}", file=sys.stderr)
        return 3

    payload = json.loads(request_path.read_text())
    requests = payload.get("requests", [])
    if not requests:
        print(json.dumps({"results": []}))
        return 0

    supported = _supported_alleles(prime_dir)

    peptides: list[str] = []
    for item in requests:
        peptide = str(item.get("peptide", "")).upper()
        if not (8 <= len(peptide) <= 14):
            continue
        name = _prime_name(str(item.get("allele", "")))
        if name is None:
            continue
        if supported and name not in supported:
            continue
        peptides.append(peptide)

    if not peptides:
        print(json.dumps({"results": []}))
        return 0

    allele_list = sorted(
        {
            _prime_name(str(item.get("allele", "")))
            for item in requests
            if _prime_name(str(item.get("allele", ""))) is not None
            and (not supported or _prime_name(str(item.get("allele", ""))) in supported)
        }
    )
    if not allele_list:
        print(json.dumps({"results": []}))
        return 0

    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False
    ) as pep_handle, tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False
    ) as out_handle:
        pep_handle.write("\n".join(peptides) + "\n")
        pep_path, out_path = pep_handle.name, out_handle.name

    env = dict(os.environ)
    # MixMHCpred invokes python3 internally: expose the platform venv first
    # (without resolving symlinks).
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")

    try:
        completed = subprocess.run(
            [
                str(tool),
                "-i",
                pep_path,
                "-a",
                ",".join(allele_list),
                "-o",
                out_path,
                "-mix",
                mix,
            ],
            capture_output=True,
            text=True,
            timeout=1800,
            env=env,
            cwd=str(prime_dir),
        )
    except subprocess.TimeoutExpired as exc:
        print(f"PRIME timed out: {exc}", file=sys.stderr)
        return 4
    finally:
        os.unlink(pep_path)

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "")[-300:]
        print(f"PRIME failed: {detail}", file=sys.stderr)
        os.unlink(out_path)
        return 5

    try:
        scores = _parse_output(Path(out_path).read_text())
    finally:
        os.unlink(out_path)

    results = []
    for item in requests:
        peptide = str(item.get("peptide", "")).upper()
        results.append(
            {"key": item.get("key"), "immunogenicity": scores.get(peptide)}
        )
    print(json.dumps({"results": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
