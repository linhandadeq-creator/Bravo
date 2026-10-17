"""Codon-level mRNA-stability objectives (transparent framework + proxies).

Mainstream mRNA design optimizes codon stability (codon-dependent mRNA
half-life) and codon-pair usage in addition to CAI/tAI. Both are implemented
here as first-class design objectives, table-replaceable:

- ``codon_stability``: mean human codon-usage weight — a transparent proxy
  (optimal codons are associated with longer half-lives). Drop a published CSC
  table at ``storage/models/codon_stability.json``
  (``{"csc": {"CTG": 0.93, ...}}``, values normalized 0..1) to replace it.
- ``codon_pair_score``: 1 − fraction of adjacent codon pairs whose members are
  both rare (bottom-quartile usage) — a transparent codon-pair penalty proxy.
  Replace with a published CPS table at ``storage/models/codon_pairs.json``
  (``{"pairs": {"CTGCTG": 0.31, ...}}``).

Provenance is always reported (``model="proxy_usage"`` /
``"proxy_rare_adjacency"`` or ``"trained_table"``); proxies are never
presented as fitted models. Research use only.
"""
from __future__ import annotations

import json

from app.blueprint.design import CODON_USAGE
from app.core.config import settings

_CODON_FREQ: dict[str, float] = {
    codon: freq for options in CODON_USAGE.values() for codon, freq in options
}
_AA_OF_CODON: dict[str, str] = {
    codon: aa for aa, options in CODON_USAGE.items() for codon, _ in options
}
_MAX_FREQ_BY_AA: dict[str, float] = {
    aa: max(freq for _, freq in options) for aa, options in CODON_USAGE.items()
}
_SORTED_FREQS = sorted(_CODON_FREQ.values())
_QUARTILE = _SORTED_FREQS[max(0, len(_SORTED_FREQS) // 4 - 1)]
_RARE = {codon for codon, freq in _CODON_FREQ.items() if freq <= _QUARTILE}

_CSC_TABLE: dict[str, float] | None = None
_PAIR_TABLE: dict[str, float] | None = None


def _load_json(name: str, key: str) -> dict | None:
    path = settings.storage_path / "models" / name
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
        table = data.get(key)
        return table if isinstance(table, dict) and table else None
    except Exception:  # noqa: BLE001
        return None


def _csc_table() -> dict[str, float] | None:
    global _CSC_TABLE
    if _CSC_TABLE is None:
        _CSC_TABLE = _load_json("codon_stability.json", "csc") or {}
    return _CSC_TABLE or None


def _pair_table() -> dict[str, float] | None:
    global _PAIR_TABLE
    if _PAIR_TABLE is None:
        _PAIR_TABLE = _load_json("codon_pairs.json", "pairs") or {}
    return _PAIR_TABLE or None


def codon_stability(codons: list[str]) -> float | None:
    """Codon stability score (0..1, higher = more stable).

    Proxy: mean usage weight normalized by the best achievable for the same
    amino-acid sequence (1.0 = all-optimal codons). Replaced by a published
    CSC table when ``storage/models/codon_stability.json`` is present.
    """
    usable = [c for c in codons if c in _CODON_FREQ or c in (_csc_table() or {})]
    if not usable:
        return None
    table = _csc_table()
    if table:
        values = [float(table.get(c, _CODON_FREQ.get(c, 0.5))) for c in usable]
        peak = sum(_MAX_FREQ_BY_AA.get(_AA_OF_CODON.get(c, ""), 1.0) for c in usable)
        if peak <= 0:
            peak = float(len(values))
        return round(max(0.0, min(1.0, sum(values) / peak)), 4)
    values = [(_AA_OF_CODON[c], _CODON_FREQ[c]) for c in usable if c in _CODON_FREQ]
    if not values:
        return None
    peak = sum(_MAX_FREQ_BY_AA.get(aa, 1.0) for aa, _ in values)
    if peak <= 0:
        return None
    return round(max(0.0, min(1.0, sum(freq for _, freq in values) / peak)), 4)


def codon_pair_score(codons: list[str]) -> float | None:
    """Codon-pair score (0..1, higher = fewer rare–rare adjacent pairs)."""
    pairs = [a + b for a, b in zip(codons, codons[1:])]
    if not pairs:
        return None
    table = _pair_table()
    if table:
        values = [float(table[p]) for p in pairs if p in table]
        if values:
            return round(max(0.0, min(1.0, sum(values) / len(values))), 4)
    rare_rare = sum(1 for a, b in zip(codons, codons[1:]) if a in _RARE and b in _RARE)
    return round(1.0 - rare_rare / len(pairs), 4)


def model_info() -> dict:
    """Provenance for both objectives (table-driven when tables are present)."""
    return {
        "codon_stability": "trained_table" if _csc_table() else "proxy_usage",
        "codon_pairs": "trained_table" if _pair_table() else "proxy_rare_adjacency",
    }
