from app.ranking import (
    DEFAULT_WEIGHTS,
    DISCLAIMER,
    CandidateRankingEngine,
    RankingInput,
    compute_score,
    normalize_weights,
    specificity_from_classification,
)


def test_weights_normalize_to_one():
    weights = normalize_weights({"presentation": 2, "expression": 2})
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert set(weights) == set(DEFAULT_WEIGHTS)


def test_score_is_bounded_and_weighted():
    components = {key: 1.0 for key in DEFAULT_WEIGHTS}
    assert compute_score(components, DEFAULT_WEIGHTS) == 100.0
    assert compute_score({key: 0.0 for key in DEFAULT_WEIGHTS}, DEFAULT_WEIGHTS) == 0.0


def test_presentation_weight_changes_ranking():
    components = {key: 0.0 for key in DEFAULT_WEIGHTS}
    components["presentation"] = 1.0
    low = compute_score(
        components,
        {"presentation": 0.1, "expression": 0.4, "mutation": 0.2, "tumor_specificity": 0.2, "variant_quality": 0.1},
    )
    high = compute_score(
        components,
        {"presentation": 0.8, "expression": 0.05, "mutation": 0.05, "tumor_specificity": 0.05, "variant_quality": 0.05},
    )
    assert high > low


def test_expression_cap_normalization():
    result = CandidateRankingEngine().rank(RankingInput(expression=50.0, expression_cap=50.0))
    assert result.components["expression"] == 1.0
    result_low = CandidateRankingEngine().rank(RankingInput(expression=25.0, expression_cap=50.0))
    assert result_low.components["expression"] == 0.5


def test_specificity_mapping():
    assert specificity_from_classification("TUMOR_ONLY") == 1.0
    assert specificity_from_classification("UNCERTAIN") == 0.5
    assert specificity_from_classification("SHARED") == 0.0
    assert specificity_from_classification(None) == 0.0


def test_score_declares_research_only():
    assert "not a clinical efficacy probability" in DISCLAIMER
    result = CandidateRankingEngine().rank(RankingInput(presentation=0.5))
    assert result.disclaimer == DISCLAIMER


def test_ranking_config_roundtrip(client):
    project_id = client.post("/api/projects", json={"name": "Ranking Project"}).json()["id"]

    default = client.get(f"/api/projects/{project_id}/ranking-config").json()
    assert default["weights"]["presentation"] == DEFAULT_WEIGHTS["presentation"]
    assert "not a clinical efficacy probability" in default["disclaimer"]

    updated = client.put(
        f"/api/projects/{project_id}/ranking-config",
        json={"weights": {"presentation": 0.6, "expression": 0.1, "mutation": 0.1, "tumor_specificity": 0.1, "variant_quality": 0.1}},
    ).json()
    assert updated["weights"]["presentation"] == 0.6

    invalid = client.put(
        f"/api/projects/{project_id}/ranking-config",
        json={"weights": {"not_a_weight": 0.5}},
    )
    assert invalid.status_code == 400


def test_clonality_normalization():
    from app.ranking.engine import normalize_clonality

    assert normalize_clonality(None) == 0.0
    assert normalize_clonality(0.25) == 0.5
    assert normalize_clonality(0.5) == 1.0
    assert normalize_clonality(1.0) == 1.0


def test_clonality_affects_score():
    from app.ranking.engine import CandidateRankingEngine, RankingInput

    engine = CandidateRankingEngine()
    clonal = engine.rank(RankingInput(presentation=0.5, clonality=0.5)).score
    subclonal = engine.rank(RankingInput(presentation=0.5, clonality=0.05)).score
    assert clonal > subclonal


def test_agretopicity_normalization():
    from app.ranking.engine import normalize_agretopicity

    assert normalize_agretopicity(None) == 0.0
    assert normalize_agretopicity(-0.2) == 0.0
    assert normalize_agretopicity(0.25) == 0.5
    assert normalize_agretopicity(0.5) == 1.0


def test_agretopicity_affects_score():
    from app.ranking.engine import CandidateRankingEngine, RankingInput

    engine = CandidateRankingEngine()
    better = engine.rank(RankingInput(presentation=0.5, agretopicity=0.5)).score
    worse = engine.rank(RankingInput(presentation=0.5, agretopicity=0.0)).score
    assert better > worse
