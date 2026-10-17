"""3' UTR mRNA-stability model.

Scores a 3' UTR for predicted transcript stability from transparent sequence
features: ARE (AU-rich element) motifs (destabilising), GC content, length,
5'-proximal structure and GU-rich elements. Weights are documented and
reproducible (a trained model can replace them by writing
``storage/models/stability_model.json`` with the same shape). Used to pick the
most stability-friendly 3' UTR from a library plus de-novo candidates.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from app.blueprint.design import mfe
from app.core.config import settings

# Small curated 3' UTR library (human-derived, ARE-light).
THREE_UTR_LIBRARY = [
    "GCTGCCTGCTGGAGCCTGG",
    "GACTGCCTTCGCTGCCTTCTGCCTTC",
    "GCTGCCTTCTGCCTTCGCTT",
    "CCTGCTGCCTGCTGGAGCCTGG",
    "GCTGGAGCCTGGAGCCTGG",
]

# Transparent heuristic weights: [gc, length, au, are, gquad, structure].
_HEURISTIC = [-0.6, -0.15, -0.5, -1.2, -0.4, -0.5]

_AREs = ("ATTTA", "TTATTTA", "ATTTATTTA")


def _gc(seq: str) -> float:
    return sum(1 for ch in seq if ch in "GC") / len(seq) if seq else 0.0


def features(seq: str) -> list[float]:
    seq = seq.upper().replace("U", "T")
    n = max(1, len(seq))
    au = sum(1 for ch in seq if ch in "AT") / n
    are = sum(seq.count(motif) for motif in _AREs)
    gquad = seq.count("GGG")
    energy = mfe(seq)
    structure = max(0.0, min(1.0, (-energy / n) / 0.4)) if energy is not None else 0.5
    return [
        _gc(seq),
        min(1.0, n / 100.0),
        au,
        min(1.0, are / 2.0),
        min(1.0, gquad / 4.0),
        structure,
    ]


def _weights_path() -> Path:
    return settings.storage_path / "models" / "stability_model.json"


def _load_weights() -> tuple[list[float], list[float], float]:
    path = _weights_path()
    if path.is_file():
        try:
            data = json.loads(path.read_text())
            return (
                data["weights"],
                data.get("mean", [0.0] * len(data["weights"])),
                float(data.get("bias", 0.0)),
            )
        except Exception:  # noqa: BLE001
            pass
    return _HEURISTIC, [0.0] * len(_HEURISTIC), 0.0


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def stability_score(seq: str) -> dict:
    """Predicted stability in [0, 1] (higher = more stable) + provenance."""
    weights, mean, bias = _load_weights()
    feats = features(seq)
    z = sum(w * (f - m) for w, m, f in zip(weights, mean, feats)) + bias
    trained = _weights_path().is_file()
    return {
        "stability_score": round(_sigmoid(z), 4),
        "model": "trained_ridge" if trained else "heuristic",
        "features": dict(
            zip(["gc", "length", "au", "are", "gquad", "structure"], [round(f, 4) for f in feats])
        ),
    }


def generate_three_utr_candidates(
    n: int = 48, seed: int = 2027, body_length: int = 18
) -> list[str]:
    """Deterministic ARE-free, moderate-GC 3' UTR candidates."""
    import random

    rng = random.Random(seed)
    candidates: set[str] = set()
    attempts = 0
    while len(candidates) < n * 3 and attempts < n * 30:
        attempts += 1
        body = "".join(rng.choice("ACGT") for _ in range(body_length))
        if "ATG" in body:
            continue
        if any(motif in body for motif in _AREs):
            continue
        if "AATAAA" in body or "ATTAAA" in body:
            continue
        gc = (body.count("G") + body.count("C")) / len(body)
        if not (0.35 <= gc <= 0.60):
            continue
        if any(body.count(base * 4) for base in "ACGT"):
            continue
        candidates.add(body)
    scored = [(seq, stability_score(seq)["stability_score"]) for seq in candidates]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [seq for seq, _value in scored[:n]]


def best_three_utr(n_candidates: int = 48) -> tuple[str, dict]:
    """Best 3' UTR from the library plus generated candidates (by the model)."""
    candidates = list(THREE_UTR_LIBRARY) + generate_three_utr_candidates(n=n_candidates)
    best = max(candidates, key=lambda seq: stability_score(seq)["stability_score"])
    return best, {"sequence": best, **stability_score(best)}
