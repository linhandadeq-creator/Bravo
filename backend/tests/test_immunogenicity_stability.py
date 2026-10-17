"""Tests for the innate-immunity / dsRNA proxies and the 3' UTR stability model."""
from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

from app.blueprint.immunogenicity import (
    cpg_count,
    dsrna_risk,
    innate_immune_score,
    longest_inverted_repeat,
    uridine_fraction,
)
from app.blueprint.stability import (
    THREE_UTR_LIBRARY,
    best_three_utr,
    features,
    generate_three_utr_candidates,
    stability_score,
)

ROOT = Path(__file__).resolve().parents[2]


# ---- dsRNA / innate immunity -------------------------------------------------


def test_longest_inverted_repeat_detects_stem():
    # AAAA ... perfect stem: "AAAAA" + loop "TTTTT" + revcomp "TTTTT"
    seq = "AAAAAGGGGGTTTTT"  # 5 A pairs with revcomp of 5 T -> stem 5
    assert longest_inverted_repeat(seq) >= 5
    assert 0 <= longest_inverted_repeat("ACGTACGT") <= 8


def test_dsrna_risk_bounds():
    assert 0.0 <= dsrna_risk("ACGTACGTACGT") <= 1.0
    assert dsrna_risk("ACGTACGT") < dsrna_risk("AAAAAAGGGGGTTTTT")


def test_uridine_and_cpg():
    assert uridine_fraction("AUAU") == 0.5
    assert cpg_count("ACGCGT") == 2


def test_innate_immune_score_bounds_and_m1psi():
    seq = "AUGGCAUUUAAUUUAUGG" * 3
    dna = seq.replace("U", "T")
    plain = innate_immune_score(dna, m1psi=False)
    modified = innate_immune_score(dna, m1psi=True)
    assert 0.0 <= plain["score"] <= 1.0
    assert modified["score"] <= plain["score"]  # m1Ψ reduces uridine-driven risk
    assert modified["uridine_effective"] < plain["uridine"]
    assert "dsrna_risk" in plain


# ---- 3' UTR stability model --------------------------------------------------


def test_stability_features_and_score():
    feats = features("GCTGCCTGCTGGAGCCTGG")
    assert len(feats) == 6
    assert all(0.0 <= f <= 1.0 for f in feats)
    result = stability_score("GCTGCCTGCTGGAGCCTGG")
    assert 0.0 <= result["stability_score"] <= 1.0
    assert result["model"] in ("heuristic", "trained_ridge")


def test_generate_three_utr_candidates_valid():
    candidates = generate_three_utr_candidates(24, seed=7)
    assert candidates == generate_three_utr_candidates(24, seed=7)  # deterministic
    assert len(candidates) == 24
    for seq in candidates:
        assert "ATG" not in seq
        assert not any(motif in seq for motif in ("ATTTA", "TTATTTA"))
        assert "AATAAA" not in seq and "ATTAAA" not in seq
        gc = (seq.count("G") + seq.count("C")) / len(seq)
        assert 0.35 <= gc <= 0.60


def test_best_three_utr_returns_scored():
    seq, selection = best_three_utr()
    assert selection["sequence"] == seq
    assert 0.0 <= selection["stability_score"] <= 1.0
    # the best library/generated candidate is never lower than the library min
    assert selection["stability_score"] >= min(
        stability_score(s)["stability_score"] for s in THREE_UTR_LIBRARY
    )


# ---- MPRA training pipeline --------------------------------------------------


def test_train_utr_model_pipeline(tmp_path):
    rng = random.Random(3)
    dataset = tmp_path / "mpra.csv"
    with open(dataset, "w", newline="") as handle:
        handle.write("sequence,value\n")
        for _ in range(200):
            seq = "".join(rng.choice("ACGT") for _ in range(20))
            gc = (seq.count("G") + seq.count("C")) / len(seq)
            handle.write(f"{seq},{gc + rng.uniform(-0.05, 0.05):.4f}\n")

    storage = tmp_path / "storage"
    storage.mkdir()
    env = {"STORAGE_DIR": str(storage), "PATH": "/usr/bin:/bin"}
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "train_utr_model.py"), str(dataset)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    model_file = storage / "models" / "utr_model.json"
    assert model_file.is_file()
    data = json.loads(model_file.read_text())
    assert len(data["weights"]) == 7
    assert data["n"] == 200
