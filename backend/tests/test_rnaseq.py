"""Tests for RNA-seq matrix quantification (v1)."""

import math

import pytest

from app.expression.rnaseq import (
    parse_expression_matrix,
    quantify,
)

PAIRED_TSV = (
    "gene_id\tgene_symbol\ttumor_tpm\tnormal_tpm\n"
    "ENSG00000141510\tTP53\t80\t4\n"
    "ENSG00000133703\tKRAS\t32\t32\n"
    "ENSG00000000003\tBRCA1\t0\t50\n"
    "ENSG00000000004\tEGFR\t12\t\n"
)

SAMPLE_MATRIX = (
    "gene_id,tumor_1,tumor_2,normal_1,normal_2\n"
    "ENSG00000141510,10,30,4,4\n"
    "ENSG00000133703,32,32,32,32\n"
)


# ---- parsing -----------------------------------------------------------------


def test_parse_paired_columns():
    rows, layout = parse_expression_matrix(PAIRED_TSV, "tsv")
    assert layout["scheme"] == "paired_columns"
    assert layout["tumor"] == ["tumor_tpm"]
    by_gene = {r["gene_id"]: r for r in rows}
    assert by_gene["ENSG00000141510"]["tumor_value"] == 80.0
    assert by_gene["ENSG00000141510"]["normal_value"] == 4.0
    assert by_gene["ENSG00000000004"]["normal_value"] is None  # missing value


def test_parse_sample_columns_with_group_means():
    rows, layout = parse_expression_matrix(
        SAMPLE_MATRIX,
        "csv",
        tumor_samples=["tumor_1", "tumor_2"],
        normal_samples=["normal_1", "normal_2"],
    )
    assert layout["scheme"] == "sample_columns"
    by_gene = {r["gene_id"]: r for r in rows}
    assert by_gene["ENSG00000141510"]["tumor_value"] == 20.0  # mean of 10, 30
    assert by_gene["ENSG00000141510"]["normal_value"] == 4.0


def test_parse_missing_sample_column_raises():
    with pytest.raises(ValueError):
        parse_expression_matrix(
            SAMPLE_MATRIX, "csv", tumor_samples=["nope"], normal_samples=["normal_1"]
        )


def test_parse_requires_group_declaration():
    with pytest.raises(ValueError):
        parse_expression_matrix(
            "gene_id,sample_a,sample_b\nG1,1,2\n", "csv"
        )


def test_parse_unknown_format_raises():
    with pytest.raises(ValueError):
        parse_expression_matrix(PAIRED_TSV, "json")


def test_parse_non_numeric_raises():
    with pytest.raises(ValueError):
        parse_expression_matrix(
            "gene_id\ttumor_tpm\tnormal_tpm\nG1\toops\t1\n", "tsv"
        )


# ---- quantification ----------------------------------------------------------


def test_quantify_log2fc_and_calls():
    rows, _ = parse_expression_matrix(PAIRED_TSV, "tsv")
    results = {r["gene_id"]: r for r in quantify(rows)}

    tp53 = results["ENSG00000141510"]  # 80 vs 4 → log2(81/5)
    assert tp53["log2_fold_change"] == round(math.log2(81 / 5), 6)
    assert tp53["is_expressed"] is True
    assert tp53["differentially_expressed"] is True

    kras = results["ENSG00000133703"]  # 32 vs 32 → 0
    assert kras["log2_fold_change"] == 0.0
    assert kras["is_expressed"] is True
    assert kras["differentially_expressed"] is False

    brca1 = results["ENSG00000000003"]  # 0 vs 50 → log2(1/51)
    assert brca1["log2_fold_change"] == round(math.log2(1 / 51), 6)
    assert brca1["is_expressed"] is False
    assert brca1["differentially_expressed"] is False

    egfr = results["ENSG00000000004"]  # normal missing → log2(13)
    assert egfr["log2_fold_change"] == round(math.log2(13), 6)
    assert egfr["differentially_expressed"] is False
    assert egfr["note"]


def test_quantify_custom_thresholds():
    rows, _ = parse_expression_matrix(PAIRED_TSV, "tsv")
    results = {r["gene_id"]: r for r in quantify(rows, expression_threshold=10.0, log2fc_threshold=1.0)}
    assert results["ENSG00000133703"]["is_expressed"] is True  # 32 >= 10
    assert results["ENSG00000000003"]["is_expressed"] is False  # 0 < 10


def test_quantify_missing_tumor():
    results = quantify([{"gene_id": "G", "tumor_value": None, "normal_value": 5.0}])
    assert results[0]["log2_fold_change"] is None
    assert results[0]["is_expressed"] is False


# ---- API ---------------------------------------------------------------------


def _ready_run(client, name):
    project_id = client.post("/api/projects", json={"name": name}).json()["id"]
    integration = client.post(f"/api/projects/{project_id}/synthetic-integration").json()
    return integration["analysis_run_id"]


def test_quantify_endpoint(client):
    run_id = _ready_run(client, "Quantify Project")
    response = client.post(
        f"/api/analysis-runs/{run_id}/expression/quantify",
        files={"file": ("matrix.tsv", PAIRED_TSV, "text/tab-separated-values")},
        data={"unit": "TPM"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["genes_quantified"] == 4
    assert body["expressed"] == 3
    assert body["differentially_expressed"] == 1
    assert body["method"] == "rnaseq-matrix-v1"
    assert body["samples"]["scheme"] == "paired_columns"

    rows = client.get(f"/api/analysis-runs/{run_id}/expression/quantification").json()
    assert len(rows) == 4
    by_gene = {r["gene_id"]: r for r in rows}
    assert by_gene["ENSG00000141510"]["log2_fold_change"] == round(math.log2(81 / 5), 6)
    assert by_gene["ENSG00000141510"]["differentially_expressed"] is True

    de = client.get(
        f"/api/analysis-runs/{run_id}/expression/quantification",
        params={"differentially_expressed": "true"},
    ).json()
    assert {r["gene_id"] for r in de} == {"ENSG00000141510"}


def test_quantify_also_ingests_records(client):
    run_id = _ready_run(client, "Quantify Records")
    client.post(
        f"/api/analysis-runs/{run_id}/expression/quantify",
        files={"file": ("matrix.tsv", PAIRED_TSV, "text/tab-separated-values")},
        data={"unit": "TPM"},
    )
    status_body = client.get(f"/api/analysis-runs/{run_id}/expression/status").json()
    assert status_body["status"] == "EXPRESSION_AVAILABLE"
    assert status_body["total"] == 4
    assert status_body["quantification"]["status"] == "QUANTIFICATION_AVAILABLE"
    assert status_body["quantification"]["total"] == 4


def test_quantify_sample_columns(client):
    run_id = _ready_run(client, "Quantify Samples")
    response = client.post(
        f"/api/analysis-runs/{run_id}/expression/quantify",
        files={"file": ("matrix.csv", SAMPLE_MATRIX, "text/csv")},
        data={"tumor_samples": "tumor_1,tumor_2", "normal_samples": "normal_1,normal_2"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["samples"]["scheme"] == "sample_columns"
    rows = client.get(f"/api/analysis-runs/{run_id}/expression/quantification").json()
    by_gene = {r["gene_id"]: r for r in rows}
    assert by_gene["ENSG00000141510"]["tumor_value"] == 20.0


def test_quantify_missing_columns_400(client):
    run_id = _ready_run(client, "Quantify Bad")
    response = client.post(
        f"/api/analysis-runs/{run_id}/expression/quantify",
        files={"file": ("matrix.csv", SAMPLE_MATRIX, "text/csv")},
    )
    assert response.status_code == 400


def test_quantify_unknown_sample_400(client):
    run_id = _ready_run(client, "Quantify Unknown")
    response = client.post(
        f"/api/analysis-runs/{run_id}/expression/quantify",
        files={"file": ("matrix.csv", SAMPLE_MATRIX, "text/csv")},
        data={"tumor_samples": "ghost", "normal_samples": "normal_1"},
    )
    assert response.status_code == 400


def test_quantify_replaces_previous(client):
    run_id = _ready_run(client, "Quantify Replace")
    client.post(
        f"/api/analysis-runs/{run_id}/expression/quantify",
        files={"file": ("m.tsv", PAIRED_TSV, "text/tab-separated-values")},
    )
    client.post(
        f"/api/analysis-runs/{run_id}/expression/quantify",
        files={"file": ("m.csv", SAMPLE_MATRIX, "text/csv")},
        data={"tumor_samples": "tumor_1,tumor_2", "normal_samples": "normal_1,normal_2"},
    )
    rows = client.get(f"/api/analysis-runs/{run_id}/expression/quantification").json()
    assert len(rows) == 2
