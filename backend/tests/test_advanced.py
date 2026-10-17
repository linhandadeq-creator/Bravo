import pytest

from app.core.config import settings
from app.prediction.mhcflurry_provider import _enumerate_windows
from app.services import self_filter
from app.simulation.representation import (
    HUMAN_PREFERRED_CODON,
    simulate_sequence,
)


def test_peptide_window_enumeration():
    context = "ACDEFGHIKLM"  # 11 distinct residues
    windows = _enumerate_windows(context, offset=5)
    # lengths 8,9,10,11 windows that contain index 5
    assert len(windows) == 10
    assert all("F" in window for window in windows)  # index 5 == 'F'
    assert _enumerate_windows(None, 5) == []
    assert _enumerate_windows("SIINFEKL", None) == ["SIINFEKL"]


def test_codon_optimized_sequence_is_deterministic_and_standard():
    peptides = ["MEGFPAAAA", "MSGKFAAAA"]
    first = simulate_sequence(peptides)
    second = simulate_sequence(peptides)
    assert first == second
    assert set(first) <= {"A", "C", "G", "U"}
    # Lysine uses the human-preferred codon AAG (-> AAG in RNA)
    assert HUMAN_PREFERRED_CODON["K"] == "AAG"
    assert HUMAN_PREFERRED_CODON["L"] == "CTG"


def test_self_filter_available_flag_default():
    assert self_filter.status()["available"] in (True, False)


def test_self_filter_detects_self_peptide(tmp_path, monkeypatch):
    proteome = tmp_path / "proteome.fasta"
    proteome.write_text(">self1\nAAAAAAAAASIINFEKLLAAAA\n")
    monkeypatch.setattr(settings, "HUMAN_PROTEOME_FASTA", str(proteome))
    self_filter._cache.clear()

    assert self_filter.is_available() is True
    assert self_filter.is_self_similar("SIINFEKLL") is True
    assert self_filter.is_self_similar("YVKLQPRST") is False


def test_design_engine_constraints_and_qc():
    from app.blueprint.design import design_construct
    from app.blueprint.sequence_qc import evaluate_sequence

    peptides = ["VVVGADGVGK", "EAAPHVAPA", "TDFGQAKLL", "ESAQRPAPA", "MEGFPAAAA"]
    designed = design_construct(peptides)
    qc = evaluate_sequence(designed)

    assert designed.rna.count("T") == 0
    assert set(designed.rna) <= {"A", "C", "G", "U"}
    assert 30.0 <= designed.gc_percent <= 70.0
    assert designed.constraints_ok is True
    assert qc.status == "PRODUCTION_READY"
    assert qc.manufacturability_score == 100.0
    assert qc.metrics["longest_homopolymer"] <= 5
    assert qc.metrics["restriction_sites"] == []
    assert qc.metrics["polya_signals"] == []
    # deterministic
    assert design_construct(peptides).dna == designed.dna
    # region map covers the whole sequence
    assert designed.regions[0].start == 0
    assert designed.regions[-1].end == len(designed.dna)


def test_production_package_and_worklist_endpoints(client):
    demo = client.post(
        "/api/one-click/generate", data={"demo": "true", "project_name": "图纸生产"}
    ).json()
    construct_id = demo["construct_id"]

    package = client.get(f"/api/constructs/{construct_id}/production-package").json()
    assert package["sequence_qc"]["status"] in ("PRODUCTION_READY", "DESIGN_FAILED")
    assert "manufacturing" in package
    assert package["manufacturing"]["ivt_template"]["t7_promoter"] == "TAATACGACTCACTATAG"
    assert "release_criteria_derived" in package

    md = client.get(
        f"/api/constructs/{construct_id}/production-package", params={"format": "markdown"}
    )
    assert md.status_code == 200
    assert "Production Blueprint Package" in md.text

    worklist = client.get(f"/api/constructs/{construct_id}/worklist")
    assert worklist.status_code == 200
    assert "peptide" in worklist.text
    assert "control_positive" in worklist.text


def test_ms_evidence_lookup(tmp_path, monkeypatch):
    import bz2

    from app.services import evidence

    path = tmp_path / "ms.csv.bz2"
    with bz2.open(path, "wt") as handle:
        handle.write("allele,peptide,measurement_value,measurement_type,measurement_source\n")
        handle.write("HLA-A*02:01,SIINFEKL,100,qualitative,mass_spec\n")
        handle.write("HLA-A*02:01,GILGFVFTL,50,quantitative,affinity\n")
    monkeypatch.setattr(settings, "EVIDENCE_MS_TRAINING", str(path))
    evidence._cache.clear()

    assert evidence.is_available() is True
    assert evidence.lookup("SIINFEKL", "HLA-A*02:01")["kind"] == "ms_ligand"
    assert evidence.lookup("GILGFVFTL", "HLA-A*02:01")["kind"] == "measured_binder"
    assert evidence.lookup("YVKLQPRST", "HLA-A*02:01")["observed"] is False


def test_population_coverage():
    from app.services.population_coverage import estimate

    result = estimate(
        ["HLA-A*02:01", "HLA-A*03:01", "HLA-B*07:02", "HLA-DRB1*15:01"]
    )
    assert set(result["per_locus"]) >= {"A", "B", "DRB1"}
    assert 0.0 < result["overall_coverage"] <= 1.0
    # Union approximation over the A-locus alleles; must exceed a single allele.
    a_cov = result["per_locus"]["A"]["coverage"]
    max_a = max(a["frequency"] for a in result["per_locus"]["A"]["alleles"])
    assert max_a < a_cov <= 1.0


def test_ranking_includes_ms_evidence():
    from app.ranking.engine import DEFAULT_WEIGHTS, compute_score

    assert "ms_evidence" in DEFAULT_WEIGHTS
    base = {"presentation": 0.5, "expression": 0.5, "mutation": 0.5,
            "tumor_specificity": 0.5, "variant_quality": 0.5}
    with_ms = compute_score({**base, "ms_evidence": 1.0}, DEFAULT_WEIGHTS)
    without_ms = compute_score({**base, "ms_evidence": 0.0}, DEFAULT_WEIGHTS)
    assert with_ms > without_ms


def test_system_manifest(client):
    manifest = client.get("/api/system/manifest").json()
    assert manifest["tools"]["app_version"]
    assert manifest["tools"]["packages"]["mhcflurry"]
    assert manifest["tools"]["packages"]["pysam"]
    assert "GRCh38" in manifest["reference_builds"]
    names = {p["name"] for p in manifest["annotation_providers"]}
    assert {"mock", "vep"} <= names
    assert "self_filter" in manifest


def test_system_self_filter_endpoint(client):
    body = client.get("/api/system/self-filter").json()
    assert "available" in body
