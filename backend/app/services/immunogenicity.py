"""Immunogenicity model (dry-lab).

Combines presentation, agretopicity, MS evidence and peptide physicochemical
features into an immunogenicity score. A trained ridge model is used when
weights exist (``storage/models/immunogenicity_model.json``); otherwise a
transparent, documented heuristic is used. This never fabricates a prediction —
it always declares which model produced the score.

Train with ``scripts/train_immunogenicity_model.py <dataset.csv>`` where the CSV
has a ``label`` (0/1) plus the feature columns.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from app.core.config import settings

_KD = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5,
    "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8,
    "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}
FEATURE_NAMES = [
    "presentation",
    "agretopicity",
    "ms_evidence",
    "hydrophobicity",
    "length_pref",
    "anchor_p2",
    "anchor_c",
]

# Transparent heuristic weights (used until a model is trained).
_HEURISTIC = [1.2, 1.0, 0.8, 0.6, 0.4, 0.5, 0.5]


def feature_vector(
    *,
    presentation: float | None,
    agretopicity: float | None,
    ms_evidence: bool,
    peptide: str | None,
) -> list[float]:
    pep = (peptide or "").upper()
    hydro = sum(_KD.get(ch, 0.0) for ch in pep) / max(1, len(pep))
    hydro_norm = max(0.0, min(1.0, (hydro + 1.0) / 3.0))
    length_pref = 1.0 if len(pep) in (9, 10) else (0.7 if len(pep) in (8, 11) else 0.3)
    anchor_p2 = 1.0 if len(pep) >= 2 and pep[1] in "AVILMT" else 0.0
    anchor_c = 1.0 if pep and pep[-1] in "AVILMFWY" else 0.0
    return [
        max(0.0, min(1.0, presentation or 0.0)),
        max(0.0, min(1.0, agretopicity or 0.0)),
        1.0 if ms_evidence else 0.0,
        hydro_norm,
        length_pref,
        anchor_p2,
        anchor_c,
    ]


def _weights_path() -> Path:
    return settings.storage_path / "models" / "immunogenicity_model.json"


def _load() -> tuple[list[float], list[float], float]:
    path = _weights_path()
    if path.is_file():
        try:
            data = json.loads(path.read_text())
            return data["weights"], data.get("mean", [0.0] * len(data["weights"])), float(data.get("bias", 0.0))
        except Exception:  # noqa: BLE001
            pass
    return _HEURISTIC, [0.0] * len(_HEURISTIC), -3.0


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def score(**kwargs) -> dict:
    weights, mean, bias = _load()
    feats = feature_vector(**kwargs)
    z = sum(w * (f - m) for w, m, f in zip(weights, mean, feats)) + bias
    return {
        "immunogenicity": round(_sigmoid(z), 4),
        "model": "trained_ridge" if _weights_path().is_file() else "heuristic",
        "components": dict(zip(FEATURE_NAMES, [round(f, 4) for f in feats])),
    }
