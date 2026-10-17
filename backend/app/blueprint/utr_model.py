"""5' UTR translation-efficiency model (dry-lab).

Moderna-class mRNA design optimises the 5' UTR for translation. This module
scores a 5' UTR sequence with a small ridge model over sequence/structure
features. If trained weights are present (``storage/models/utr_model.json``)
they are used; otherwise a transparent, documented heuristic is used so the
platform never fabricates a prediction.

Train on a public MPRA dataset (e.g. Sample et al. 2019 5' UTR MPRA) with::

    python scripts/train_utr_model.py <dataset.csv>   # columns: sequence,value
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from app.blueprint.design import mfe
from app.core.config import settings

_STANDARD = set("ACGTU")

# Small ATG-free 5' UTR library (ends in a Kozak context); the designer picks
# the highest-scoring entry with the translation-efficiency model.
FIVE_UTR_LIBRARY = [
    "GGGAAACGCCACC",
    "GCCGCCACC",
    "CGCGCCACC",
    "GCCACC",
    "GGGACCCGCCACC",
    "ACACGCCACC",
]

# Small 3' UTR library; the designer picks the most stability-friendly entry.
THREE_UTR_LIBRARY = [
    "GCTGCCTGCTGGAGCCTGG",
    "GACTGCCTTCGCTGCCTTCTGCCTTC",
    "GCTGCCTTCTGCCTTCGCTT",
]


def _gc(seq: str) -> float:
    if not seq:
        return 0.0
    return sum(1 for ch in seq if ch in "GC") / len(seq)


def features(seq: str) -> list[float]:
    seq = seq.upper().replace("U", "T")
    n = max(1, len(seq))
    gc = _gc(seq)
    uaug = seq.count("ATG")
    # longest upstream ORF (ATG..stop) length
    uorf = 0
    for i in range(0, len(seq) - 2):
        if seq[i : i + 3] == "ATG":
            for j in range(i + 3, len(seq) - 2, 3):
                if seq[j : j + 3] in ("TAA", "TAG", "TGA"):
                    uorf = max(uorf, j + 3 - i)
                    break
    gquad = seq.count("GGG")
    kozak = 1.0 if "GCCACC" in seq else 0.0
    energy = mfe(seq)
    # normalise the (negative) MFE per nucleotide against a soft scale
    structure = max(0.0, min(1.0, (-energy / n) / 0.4)) if energy is not None else 0.5
    return [
        gc,
        min(1.0, n / 100.0),
        min(1.0, uaug / 3.0),
        min(1.0, uorf / 30.0),
        min(1.0, gquad / 4.0),
        kozak,
        structure,
    ]


# Transparent heuristic weights (used until a model is trained).
_HEURISTIC = [-0.8, -0.2, -0.6, -0.5, -0.4, 0.5, -0.7]


def _weights_path() -> Path:
    return settings.storage_path / "models" / "utr_model.json"


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


def score(seq: str) -> dict:
    """Return a translation-efficiency score in [0,1] plus provenance."""
    weights, mean, bias = _load_weights()
    feats = features(seq)
    z = sum(w * (f - m) for w, m, f in zip(weights, mean, feats)) + bias
    value = round(_sigmoid(z), 4)
    trained = _weights_path().is_file()
    return {
        "utr_score": value,
        "model": "trained_ridge" if trained else "heuristic",
        "features": dict(
            zip(
                ["gc", "length", "uaug", "uorf", "gquad", "kozak", "structure"],
                [round(f, 4) for f in feats],
            )
        ),
    }


def generate_utr_candidates(
    n: int = 96, seed: int = 2026, body_length: int = 8, kozak: str = "GCCACC"
) -> list[str]:
    """Generate de-novo ATG-free 5' UTR candidates (deterministic).

    Random ATG-free bodies of ``body_length`` nt (GC-balanced) appended to a
    Kozak context; candidates are scored with the translation model and the
    top ``n`` returned. This turns the model into a *generative* UTR designer
    instead of only scoring a fixed library.
    """
    import random

    rng = random.Random(seed)
    candidates: set[str] = set()
    attempts = 0
    while len(candidates) < n * 3 and attempts < n * 30:
        attempts += 1
        body = "".join(rng.choice("ACGT") for _ in range(body_length))
        candidate = body + kozak
        # A UTR must not smuggle in forbidden signals: upstream ATG, cryptic
        # poly(A)/splice motifs, long homopolymers, or extreme GC.
        if "ATG" in candidate:
            continue
        if any(motif in candidate for motif in ("AATAAA", "ATTAAA", "GTAAGT")):
            continue
        gc = (candidate.count("G") + candidate.count("C")) / len(candidate)
        if not (0.35 <= gc <= 0.65):
            continue
        if any(candidate.count(base * 4) for base in "ACGT"):
            continue
        candidates.add(candidate)
    scored = [(seq, score(seq)["utr_score"]) for seq in candidates]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [seq for seq, _value in scored[:n]]


def best_utr(n_candidates: int = 96) -> str:
    """Best 5' UTR from the library plus de-novo generated candidates."""
    candidates = list(FIVE_UTR_LIBRARY) + generate_utr_candidates(n=n_candidates)
    return max(candidates, key=lambda seq: score(seq)["utr_score"])
