def test_readiness_blocked_without_hla_and_expression(client, annotated_run):
    run_id = annotated_run["run_id"]

    response = client.get(f"/api/analysis-runs/{run_id}/neoantigen-readiness")
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "HLA_UNAVAILABLE" in detail
    assert "EXPRESSION_UNAVAILABLE" in detail

    status = client.get(f"/api/analysis-runs/{run_id}/integration-status").json()
    assert status["status"] == "BLOCKED"
    check_ids = {c["id"]: c["status"] for c in status["checks"]}
    assert check_ids["hla"] == "fail"
    assert check_ids["expression"] == "fail"


def test_readiness_requires_valid_hla(client, annotated_run):
    run_id = annotated_run["run_id"]
    client.post(
        f"/api/analysis-runs/{run_id}/hla",
        json={"alleles": [{"allele": "HLA-A*02:01", "class": "II"}]},
    )
    response = client.get(f"/api/analysis-runs/{run_id}/neoantigen-readiness")
    assert response.status_code == 409
    assert "HLA_INVALID" in response.json()["detail"]


def test_synthetic_integration_is_ready_and_linked(client):
    project_id = client.post(
        "/api/projects", json={"name": "Integration Project"}
    ).json()["id"]

    response = client.post(f"/api/projects/{project_id}/synthetic-integration")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "READY"
    assert body["hla_status"] == "HLA_AVAILABLE"
    assert body["expression_status"] == "EXPRESSION_AVAILABLE"
    # MOCKGENE1 and MOCKGENE2 are both annotated and expressed.
    assert set(body["linked_genes"]) >= {"MOCKGENE1", "MOCKGENE2"}

    run_id = body["analysis_run_id"]
    readiness = client.get(f"/api/analysis-runs/{run_id}/neoantigen-readiness")
    assert readiness.status_code == 200
    report = readiness.json()
    assert report["status"] == "READY"
    assert report["genes_without_expression"] == []

    hla = client.get(f"/api/analysis-runs/{run_id}/hla").json()
    assert len(hla) == 6
    assert {p["allele_class"] for p in hla} == {"I", "II"}

    expression = client.get(f"/api/analysis-runs/{run_id}/expression").json()
    assert any(r["gene_symbol"] == "MOCKGENE1" for r in expression)
    assert any(r["level"] == "GENE" for r in expression)
    assert any(r["level"] == "TRANSCRIPT" for r in expression)
