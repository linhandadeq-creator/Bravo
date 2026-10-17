"""Self-protein off-target (self-similarity) safety filter.

When a human reference proteome FASTA is configured
(``settings.HUMAN_PROTEOME_FASTA``), a 9-mer index is built (64-bit hashes in a
sorted NumPy array) and peptides that exactly match a self 9-mer are flagged so
they can be excluded. If no proteome is configured the filter is explicitly
unavailable — it never silently passes.
"""
from __future__ import annotations

import os
import zlib
from array import array
from pathlib import Path

import numpy as np

from app.core.config import settings

_STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")
_cache: dict[str, np.ndarray] = {}


def _proteome_path() -> str | None:
    path = (settings.HUMAN_PROTEOME_FASTA or "").strip()
    if path and os.path.isfile(path):
        return path
    return None


def is_available() -> bool:
    return _proteome_path() is not None


def status() -> dict:
    path = _proteome_path()
    return {
        "available": path is not None,
        "proteome": path,
        "indexed": path in _cache if path else False,
        "reason": None
        if path
        else "HUMAN_PROTEOME_FASTA is not configured; self-similarity filter is off.",
    }


def _hash9(kmer: str) -> int:
    forward = zlib.crc32(kmer.encode())
    reverse = zlib.crc32(kmer[::-1].encode())
    return (forward << 32) | reverse


def _index_path(path: str) -> Path:
    cache_dir = settings.storage_path / "self_filter"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{Path(path).name}.npy"


def _build_index(path: str) -> np.ndarray:
    hashes = array("Q")
    buffer: list[str] = []

    def _add(sequence: str) -> None:
        sequence = "".join(ch for ch in sequence.upper() if ch in _STANDARD_AA)
        for i in range(len(sequence) - 8):
            hashes.append(_hash9(sequence[i : i + 9]))

    with open(path) as handle:
        for line in handle:
            if line.startswith(">"):
                if buffer:
                    _add("".join(buffer))
                    buffer = []
            else:
                buffer.append(line.strip())
    if buffer:
        _add("".join(buffer))
    unique = np.unique(np.frombuffer(hashes, dtype=np.uint64))
    np.save(_index_path(path), unique)
    return unique


def _load_index(path: str) -> np.ndarray:
    if path in _cache:
        return _cache[path]
    index_file = _index_path(path)
    if index_file.exists() and index_file.stat().st_mtime >= os.path.getmtime(path):
        unique = np.load(index_file)
    else:
        unique = _build_index(path)
    _cache[path] = unique
    return unique


def is_self_similar(peptide: str | None) -> bool:
    if not peptide or not is_available():
        return False
    peptide = peptide.upper()
    if len(peptide) < 9:
        return False
    index = _load_index(_proteome_path() or "")
    for i in range(len(peptide) - 8):
        kmer = peptide[i : i + 9]
        if any(ch not in _STANDARD_AA for ch in kmer):
            continue
        h = np.uint64(_hash9(kmer))
        pos = int(np.searchsorted(index, h))
        if pos < len(index) and index[pos] == h:
            return True
    return False
