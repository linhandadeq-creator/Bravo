"""Tests for the P2 sequence-design metrics: tAI, expression score, stability
and generative 5' UTR candidates."""
from __future__ import annotations

from app.blueprint.design import DesignConfig, _tai, design_construct
from app.blueprint.formats import FORMATS
from app.blueprint.package import build_sequence_design
from app.blueprint.utr_model import generate_utr_candidates


def test_tai_bounds_and_monotonic():
    assert _tai(["GCC"]) == 1.0  # GCC is the most adaptive Ala codon
    assert _tai(["ATA"]) < 0.3  # rare Ile codon
    assert _tai(["CTG"]) > _tai(["TTA"])  # preferred vs rare Leu codon
    assert 0.0 <= _tai(["GCC", "AAC", "CTG", "GAT"]) <= 1.0


def test_design_exposes_expression_metrics():
    for fmt in FORMATS:
        designed = design_construct(["MEGFPAAAA", "MSGKFAAAA"], DesignConfig(format=fmt))
        assert 0.0 <= designed.tai <= 1.0, fmt
        assert 0.0 <= designed.expression_score <= 100.0, fmt
        assert 0.0 <= designed.stability_score <= 1.0, fmt
        assert 0.0 <= designed.u_content <= 1.0, fmt
        assert designed.mfe_per_nt is None or designed.mfe_per_nt <= 0.0


def test_package_exposes_expression_score():
    designed = design_construct(["SLLPAIVEL", "LLWNGPMAV"])
    design = build_sequence_design(designed)
    for key in ("tai", "expression_score", "stability_score", "u_content", "mfe_per_nt"):
        assert key in design
    assert 0.0 <= design["expression_score"] <= 100.0


def test_package_exposes_codon_and_ivt_metrics():
    designed = design_construct(["SLLPAIVEL", "LLWNGPMAV"])
    design = build_sequence_design(designed)
    assert 0.0 <= design["codon_stability"] <= 1.0
    assert 0.0 <= design["codon_pair_score"] <= 1.0
    assert design["codon_metrics_model"]["codon_stability"] in (
        "proxy_usage",
        "trained_table",
    )
    assert design["ivt_start"]["model"] == "transparent_rule"
    assert design["poly_a_design"]["recommended"] in (60, 80, 100, 120, 150)


def test_generate_utr_candidates_valid_and_deterministic():
    first = generate_utr_candidates(20, seed=1)
    second = generate_utr_candidates(20, seed=1)
    assert first == second  # deterministic
    assert len(first) == 20
    for seq in first:
        assert seq.endswith("GCCACC")
        assert "ATG" not in seq
        assert not any(motif in seq for motif in ("AATAAA", "ATTAAA", "GTAAGT"))
