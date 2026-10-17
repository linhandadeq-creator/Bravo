from app.blueprint.utr_model import FIVE_UTR_LIBRARY, features, score
from app.blueprint.design import design_construct


def test_feature_vector_shape():
    feats = features("GGGAAACGCCACC")
    assert len(feats) == 7
    assert all(0.0 <= f <= 1.0 for f in feats)


def test_score_is_bounded_and_declares_model():
    result = score("GGGAAACGCCACC")
    assert 0.0 <= result["utr_score"] <= 1.0
    assert result["model"] in ("heuristic", "trained_ridge")
    assert "features" in result


def test_design_picks_valid_utr():
    """The designer now picks from the library plus de-novo generated
    candidates — assert the chosen 5'UTR is a valid, scored, translation-
    friendly UTR (Kozak-ending, ATG-free, no forbidden motifs)."""
    designed = design_construct(["VVVGADGVGK", "EAAPHVAPA"])
    first = next(r for r in designed.regions if r.type == "FIVE_PRIME_UTR")
    utr = designed.dna[first.start : first.end]
    assert utr.endswith("GCCACC")
    assert "ATG" not in utr
    assert not any(motif in utr for motif in ("AATAAA", "ATTAAA", "GTAAGT"))
    assert designed.utr_selection is not None
    assert 0.0 <= designed.utr_selection["utr_score"] <= 1.0
