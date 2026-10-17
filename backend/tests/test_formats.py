"""Tests for the extended simulation formats (circRNA / saRNA) and UTR scoring."""

import pytest

from app.blueprint.design import DesignConfig, design_construct
from app.blueprint.formats import (
    FORBIDDEN_MOTIFS,
    FORBIDDEN_RE,
    FORMAT_CIRCRNA,
    FORMAT_MRNA_LNP,
    FORMAT_SARNA,
    FORMATS,
    IRES,
    PIE_E1,
    PIE_E2,
    REPLICASE,
    SGP,
    resolve_format,
)
from app.blueprint.sequence_qc import PASS, evaluate_sequence
from app.simulation.representation import build_representation, simulate_sequence


def _no_forbidden(seq: str) -> bool:
    seq = seq.upper()
    if any(m in seq for m in FORBIDDEN_MOTIFS):
        return False
    if any(m in seq for m in FORBIDDEN_RE):
        return False
    run = 1
    best = 1
    for i in range(1, len(seq)):
        run = run + 1 if seq[i] == seq[i - 1] else 1
        best = max(best, run)
    return best <= 5


# ---- scaffold sanity ---------------------------------------------------------


@pytest.mark.parametrize("seq", [PIE_E1, PIE_E2, IRES, REPLICASE, SGP])
def test_scaffolds_respect_constraints(seq):
    assert 35.0 <= (100.0 * sum(1 for c in seq if c in "GC") / len(seq)) <= 65.0
    assert _no_forbidden(seq)


def test_scaffolds_deterministic():
    from app.blueprint.formats import _make_scaffold

    assert _make_scaffold(66, seed=401, label="x") == PIE_E1
    assert _make_scaffold(600, seed=404, label="x") == REPLICASE


def test_resolve_format():
    assert resolve_format("mRNA-LNP") == FORMAT_MRNA_LNP
    assert resolve_format("circRNA") == FORMAT_CIRCRNA
    assert resolve_format("saRNA") == FORMAT_SARNA
    with pytest.raises(ValueError):
        resolve_format("mRNA")
    with pytest.raises(ValueError):
        resolve_format(None)


# ---- design engine per format ------------------------------------------------


def _types(designed):
    return [r.type for r in designed.regions]


def test_circrna_design_layout():
    designed = design_construct(
        ["VVVGADGVGK", "EAAPHVAPA"], DesignConfig(format=FORMAT_CIRCRNA)
    )
    assert designed.circular is True
    assert designed.format_key == FORMAT_CIRCRNA
    assert designed.ligation_junction == 0
    types = _types(designed)
    assert "PIE_EXON" in types and "IRES" in types
    assert "POLY_A" not in types and "FIVE_PRIME_UTR" not in types
    assert designed.dna.startswith(PIE_E1)
    assert designed.dna.endswith(PIE_E2)
    assert IRES in designed.dna
    assert "U" in designed.rna and "T" not in designed.rna


def test_sarna_design_layout():
    designed = design_construct(
        ["VVVGADGVGK", "EAAPHVAPA"], DesignConfig(format=FORMAT_SARNA)
    )
    assert designed.circular is False
    types = _types(designed)
    assert "REPLICASE" in types and "SUBGENOMIC_PROMOTER" in types
    assert "POLY_A" in types and "FIVE_PRIME_UTR" in types
    assert REPLICASE in designed.dna and SGP in designed.dna
    assert designed.dna.endswith("A" * 120)


def test_mrna_lnp_layout_unchanged():
    designed = design_construct(["VVVGADGVGK"])
    types = _types(designed)
    assert "REPLICASE" not in types and "IRES" not in types and "PIE_EXON" not in types
    assert "POLY_A" in types
    assert designed.utr_selection is not None
    assert "utr_score" in designed.utr_selection
    assert "model" in designed.utr_selection
    assert designed.utr_selection["sequence"] in designed.dna


def test_all_formats_pass_sequence_qc():
    peptides = ["MEGFPAAAA", "MSGKFAAAA"]
    for fmt in FORMATS:
        designed = design_construct(peptides, DesignConfig(format=fmt))
        qc = evaluate_sequence(designed)
        assert qc.status == PASS, (fmt, qc.checks)


def test_overlapping_windows_repeat_repair():
    """Overlapping epitope windows from the same variant (AKT1 E17K-like)
    share long identical stretches; the repeat-repair pass must break them."""
    peptides = ["HKRGKYIKTW", "LHKRGKYIKTW", "RGKYIKTWRP", "GKYIKTWRPR"]
    designed = design_construct(peptides, DesignConfig(format="mRNA-LNP"))
    qc = evaluate_sequence(designed)
    assert qc.status == PASS, qc.checks
    assert qc.metrics["longest_direct_repeat"] < 12


def test_immunostimulatory_motif_repair():
    """I-Y dipeptides encode AUUUA; the motif-repair pass must remove it."""
    peptides = ["ATIYAAFGKL", "ATIYAAFGKM", "TIYAAFGKLS"]
    designed = design_construct(peptides, DesignConfig(format="mRNA-LNP"))
    qc = evaluate_sequence(designed)
    assert qc.status == PASS, qc.checks
    assert qc.metrics["au_rich_motifs"] <= 2


def test_simulate_sequence_formats():
    peptides = ["MSGKFAAAA", "MEGFPAAAA"]
    mrna = simulate_sequence(peptides, FORMAT_MRNA_LNP)
    circ = simulate_sequence(peptides, FORMAT_CIRCRNA)
    sa = simulate_sequence(peptides, FORMAT_SARNA)
    assert "U" in mrna and len(circ) < len(sa)
    assert IRES.replace("T", "U") in circ
    assert REPLICASE.replace("T", "U") in sa


def test_representation_per_format():
    assert build_representation(2, FORMAT_MRNA_LNP) == (
        "[5PRIME] [ANTIGEN_001] [SPACER] [ANTIGEN_002] [3PRIME]"
    )
    assert build_representation(2, FORMAT_CIRCRNA) == (
        "[PIE_3P] [IRES] [ANTIGEN_001] [SPACER] [ANTIGEN_002] [PIE_5P]"
    )
    assert build_representation(1, FORMAT_SARNA) == (
        "[5PRIME] [REPLICASE] [SGP] [ANTIGEN_001] [3PRIME]"
    )
    with pytest.raises(ValueError):
        build_representation(1, "mRNA")


# ---- API-level ---------------------------------------------------------------


def _ready_run(client, name, provider="mock"):
    project_id = client.post("/api/projects", json={"name": name}).json()["id"]
    integration = client.post(f"/api/projects/{project_id}/synthetic-integration").json()
    run_id = integration["analysis_run_id"]
    client.post(
        f"/api/analysis-runs/{run_id}/neoantigen/run", json={"provider": provider}
    )
    return project_id, run_id


def _candidates(client, run_id, params=None):
    return client.get(
        f"/api/analysis-runs/{run_id}/neoantigen-candidates", params=params or {}
    ).json()


def test_create_circrna_construct_via_api(client):
    _, run_id = _ready_run(client, "circRNA Project")
    ranked = _candidates(client, run_id, {"status": "RANKED"})
    ids = [c["id"] for c in ranked[:2]]

    response = client.post(
        f"/api/analysis-runs/{run_id}/constructs",
        json={"candidate_ids": ids, "simulation_format": "circRNA"},
    )
    assert response.status_code == 201
    construct = response.json()
    assert construct["status"] == "VALIDATED_SIMULATION"
    assert construct["construct_representation"] == (
        "[PIE_3P] [IRES] [ANTIGEN_001] [SPACER] [ANTIGEN_002] [PIE_5P]"
    )
    package = construct["simulation_output"]
    assert package["simulation_format"] == "circRNA"
    assert package["sequence_design"]["circular"] is True
    assert package["sequence_design"]["ligation_junction"] == 0
    sop = package["sections"]["laboratory_manufacturing_sop"]["steps"]
    assert any("circularization" in step.lower() for step in sop)
    assert not any("capping" in step.lower() for step in sop)
    assert package["mrna_chemistry"]["cap"] is None
    qc_metrics = package["sequence_qc"]["metrics"]
    assert qc_metrics["format"] == "circRNA" and qc_metrics["circular"] is True


def test_create_sarna_construct_via_api(client):
    _, run_id = _ready_run(client, "saRNA Project")
    ranked = _candidates(client, run_id, {"status": "RANKED"})
    ids = [c["id"] for c in ranked[:2]]

    response = client.post(
        f"/api/analysis-runs/{run_id}/constructs",
        json={"candidate_ids": ids, "simulation_format": "saRNA"},
    )
    assert response.status_code == 201
    construct = response.json()
    assert construct["status"] == "VALIDATED_SIMULATION"
    assert construct["construct_representation"] == (
        "[5PRIME] [REPLICASE] [SGP] [ANTIGEN_001] [SPACER] [ANTIGEN_002] [3PRIME]"
    )
    package = construct["simulation_output"]
    assert package["mrna_chemistry"]["replicase"]
    criteria = package["release_criteria_derived"]
    assert "full_length_replicon_min" in criteria


def test_invalid_format_rejected(client):
    _, run_id = _ready_run(client, "Bad Format Project")
    ranked = _candidates(client, run_id, {"status": "RANKED"})
    response = client.post(
        f"/api/analysis-runs/{run_id}/constructs",
        json={"candidate_ids": [ranked[0]["id"]], "simulation_format": "mRNA"},
    )
    assert response.status_code == 422


def test_blueprint_segments_for_formats(client):
    _, run_id = _ready_run(client, "Blueprint Formats")
    ranked = _candidates(client, run_id, {"status": "RANKED"})
    ids = [c["id"] for c in ranked[:2]]

    circ = client.post(
        f"/api/analysis-runs/{run_id}/constructs",
        json={"candidate_ids": ids, "simulation_format": "circRNA"},
    ).json()
    blueprint = client.get(f"/api/constructs/{circ['id']}/blueprint").json()
    seg_types = [s["type"] for s in blueprint["segments"]]
    assert seg_types[0] == "PIE_EXON" and "IRES" in seg_types
    assert blueprint["circular"] is True

    sa = client.post(
        f"/api/analysis-runs/{run_id}/constructs",
        json={"candidate_ids": ids, "simulation_format": "saRNA"},
    ).json()
    blueprint = client.get(f"/api/constructs/{sa['id']}/blueprint").json()
    seg_types = [s["type"] for s in blueprint["segments"]]
    assert "REPLICASE" in seg_types and "SUBGENOMIC_PROMOTER" in seg_types
    assert blueprint["circular"] is False


def test_one_click_demo_with_sarna(client):
    response = client.post(
        "/api/one-click/generate", data={"demo": "true", "simulation_format": "saRNA"}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "SUCCESS"
    blueprint = result.get("blueprint") or {}
    assert blueprint.get("simulation_format") == "saRNA"


def test_design_exposes_translation_metrics():
    """P2: designs report tAI, expression score, stability and uridine content."""
    designed = design_construct(["MEGFPAAAA", "MSGKFAAAA"], DesignConfig(format="mRNA-LNP"))
    assert 0.0 <= designed.tai <= 1.0
    assert 0.0 <= designed.expression_score <= 100.0
    assert 0.0 <= designed.stability_score <= 1.0
    assert 0.0 <= designed.u_content <= 1.0
    assert designed.mfe_per_nt is not None

    from app.blueprint.package import build_sequence_design

    design = build_sequence_design(designed)
    assert design["tai"] == designed.tai
    assert design["expression_score"] == designed.expression_score
    assert design["utr_selection"]["utr_score"] >= 0.0
