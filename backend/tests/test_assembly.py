import pytest

from app.blueprint.assembly import (
    LINKERS,
    assemble,
    build_protein,
    junction_windows,
    order_epitopes,
)
from app.services.population_coverage import estimate

EPITOPES = [
    {"peptide": "SLLPAIVEL", "hla": "HLA-A*02:01", "score": 0.27},
    {"peptide": "LLWNGPMAV", "hla": "HLA-A*02:01", "score": 0.12},
    {"peptide": "KVLEYVIKV", "hla": "HLA-A*02:01", "score": 0.31},
]


def test_build_protein_and_junctions():
    protein, junctions = build_protein(["AAAABBBB", "CCCCDDDD"], "GPGPG")
    assert protein == "AAAABBBBGPGPGCCCCDDDD"
    assert junctions == [8]


def test_unknown_linker_and_strategy_rejected():
    with pytest.raises(ValueError):
        assemble(EPITOPES, linker="XYZ")
    with pytest.raises(ValueError):
        assemble(EPITOPES, strategy="magic")


def test_invalid_peptide_rejected():
    with pytest.raises(ValueError):
        assemble([{"peptide": "AAAA*AAA"}])


def test_order_immunogenicity_is_deterministic():
    first = order_epitopes(EPITOPES, "immunogenicity", LINKERS["GPGPG"])
    second = order_epitopes(EPITOPES, "immunogenicity", LINKERS["GPGPG"])
    assert [e["peptide"] for e in first] == [e["peptide"] for e in second]
    assert first[0]["peptide"] == "KVLEYVIKV"


def test_order_coverage_favours_common_allele():
    common = {"peptide": "SLLPAIVEL", "hla": "HLA-A*02:01"}
    rare = {"peptide": "KVLEYVIKV", "hla": "HLA-A*68:02"}
    freq_common = estimate(["HLA-A*02:01"])["overall_coverage"]
    freq_rare = estimate(["HLA-A*68:02"])["overall_coverage"]
    assert freq_common >= freq_rare
    ordered = order_epitopes([rare, common], "coverage", "")
    assert ordered[0]["hla"] == "HLA-A*02:01"


def test_junction_windows_span_boundary():
    protein, junctions = build_protein(["SLLPAIVEL", "LLWNGPMAV"], "AAY")
    windows = junction_windows(protein, junctions[0])
    assert windows
    assert all(8 <= len(w) <= 11 for w in windows)
    for window in windows:
        assert window in protein


def test_analyze_junctions_report_structure():
    result = assemble(EPITOPES, strategy="input")
    report = result["report"]
    assert report["n_junctions"] == 2
    assert report["windows_checked"] > 0
    assert set(report.keys()) >= {
        "n_junctions",
        "windows_checked",
        "self_similar_count",
        "duplicated_count",
        "self_filter",
        "junctions",
    }
    assert len(report["junctions"]) == 2


def test_junction_strategy_is_deterministic():
    first = assemble(EPITOPES, strategy="junction")
    second = assemble(EPITOPES, strategy="junction")
    assert first["protein"] == second["protein"]


def test_assemble_with_design_exposes_new_metrics():
    result = assemble(EPITOPES[:2], strategy="input", design=True)
    design = result["design"]
    assert 0.0 <= design["codon_stability"] <= 1.0
    assert 0.0 <= design["codon_pair_score"] <= 1.0
    assert design["ivt_start"]["model"] == "transparent_rule"
    assert design["poly_a_design"]["chosen"] >= 60
    assert design["constraints_ok"] is True


def test_assembly_api(client):
    response = client.post(
        "/api/blueprint/assembly",
        json={
            "epitopes": [{"peptide": "SLLPAIVEL", "hla": "HLA-A*02:01"}],
            "linker": "AAY",
            "strategy": "input",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["protein"] == "SLLPAIVEL"
    assert body["linker_sequence"] == "AAY"

    bad = client.post(
        "/api/blueprint/assembly",
        json={"epitopes": [{"peptide": "SLLPAIVEL"}], "linker": "XYZ"},
    )
    assert bad.status_code == 422

    options = client.get("/api/blueprint/assembly/options")
    assert options.status_code == 200
    assert "GPGPG" in options.json()["linkers"]
