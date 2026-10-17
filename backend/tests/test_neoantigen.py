import io


def _make_run_ready(client, run_id):
    client.post(
        f"/api/analysis-runs/{run_id}/hla",
        json={
            "alleles": [
                {"allele": "HLA-A*02:01", "class": "I"},
                {"allele": "HLA-B*07:02", "class": "I"},
            ],
            "source": "manual",
            "method": "manual",
            "version": "1.0.0",
        },
    )
    expression = (
        "gene_id\tgene_symbol\ttranscript_id\texpression_value\tunit\n"
        "ENSG_MOCK00001.3\tMOCKGENE1\tENST_MOCK00001.1\t12.5\tTPM\n"
        "ENSG_MOCK00002\tMOCKGENE2\tENST_MOCK00002.1\t8.0\tTPM\n"
    )
    client.post(
        f"/api/analysis-runs/{run_id}/expression/upload",
        files={
            "file": ("expression.tsv", io.BytesIO(expression.encode()), "text/tab-separated-values")
        },
    )


def test_germline_shared_variants_never_become_candidates(client, annotated_run):
    """Tumour==normal records are germline (SHARED) and must be rejected."""
    run_id = annotated_run["run_id"]
    _make_run_ready(client, run_id)
    client.post(f"/api/analysis-runs/{run_id}/neoantigen/run", json={"provider": "mock"})

    candidates = client.get(
        f"/api/analysis-runs/{run_id}/neoantigen-candidates"
    ).json()
    assert candidates
    for candidate in candidates:
        assert candidate["status"] == "REJECTED"
        assert candidate["mutation_evidence"]["reject_reason"] == "GERMLINE_SHARED"


def _integration_run(client, name="Neoantigen Project"):
    project_id = client.post("/api/projects", json={"name": name}).json()["id"]
    response = client.post(f"/api/projects/{project_id}/synthetic-integration").json()
    assert response["status"] == "READY"
    return project_id, response["analysis_run_id"]


def test_engine_generates_predicts_and_ranks(client):
    _, run_id = _integration_run(client)

    summary = client.post(
        f"/api/analysis-runs/{run_id}/neoantigen/run", json={"provider": "mock"}
    ).json()
    assert summary["generated"] > 0
    assert summary["rejected"] > 0
    assert summary["prediction"]["provider_status"] == "MOCK"
    assert summary["prediction"]["is_mock"] is True
    assert summary["ranking"]["ranked"] > 0

    candidates = client.get(
        f"/api/analysis-runs/{run_id}/neoantigen-candidates"
    ).json()
    assert candidates

    genes = {c["gene"] for c in candidates}
    assert {"MOCKGENE1", "MOCKGENE2"} <= genes

    protein_changes = {c["protein_change"] for c in candidates}
    assert "p.K2E" in protein_changes
    assert "p.P2S" in protein_changes

    for candidate in candidates:
        assert candidate["peptide_representation"]
        assert candidate["hla_allele"]
        if candidate["gene"]:
            assert candidate["peptide_sequence"]
        if candidate["status"] == "REJECTED":
            assert candidate["ranking_score"] is None
        else:
            assert candidate["prediction_status"] == "MOCK"
            assert candidate["status"] == "RANKED"
            assert candidate["ranking_score"] is not None
            assert candidate["ranking_evidence"]["disclaimer"]


def test_engine_records_ranking_configuration_on_run(client):
    _, run_id = _integration_run(client, "Ranking Record Project")
    client.post(f"/api/analysis-runs/{run_id}/neoantigen/run", json={"provider": "mock"})

    # The configuration used is snapshotted onto the run via the candidate field.
    candidates = client.get(
        f"/api/analysis-runs/{run_id}/neoantigen-candidates"
    ).json()
    ranked = [c for c in candidates if c["status"] == "RANKED"]
    assert ranked
    assert all(c["ranking_configuration_id"] for c in ranked)


def test_unavailable_provider_does_not_substitute_mock(client):
    _, run_id = _integration_run(client, "Unavailable Provider Project")

    summary = client.post(
        f"/api/analysis-runs/{run_id}/neoantigen/run", json={"provider": "external"}
    ).json()
    assert summary["prediction"]["provider_status"] == "UNAVAILABLE"
    assert summary["prediction"]["predicted"] == 0
    assert summary["ranking"]["ranked"] == 0

    candidates = client.get(
        f"/api/analysis-runs/{run_id}/neoantigen-candidates"
    ).json()
    active = [c for c in candidates if c["status"] != "REJECTED"]
    assert active
    for candidate in active:
        assert candidate["prediction_status"] == "UNAVAILABLE"
        assert candidate["ranking_score"] is None
        assert "PREDICTION UNAVAILABLE" in candidate["error_message"]


def test_candidate_detail_has_provenance(client):
    _, run_id = _integration_run(client, "Provenance Project")
    client.post(f"/api/analysis-runs/{run_id}/neoantigen/run", json={"provider": "mock"})

    candidates = client.get(
        f"/api/analysis-runs/{run_id}/neoantigen-candidates", params={"sort": "score_desc"}
    ).json()
    target = candidates[0]

    detail = client.get(f"/api/neoantigen-candidates/{target['id']}").json()
    assert detail["candidate"]["id"] == target["id"]
    assert detail["variant"] is not None
    assert detail["annotation"] is not None
    assert detail["predictions"]
    assert detail["predictions"][0]["provider"] == "mock"
    assert detail["provider_is_mock"] is True
    assert "not a clinical efficacy probability" in detail["disclaimer"]


def test_candidate_filtering_and_search(client):
    _, run_id = _integration_run(client, "Filter Project")
    client.post(f"/api/analysis-runs/{run_id}/neoantigen/run", json={"provider": "mock"})

    ranked = client.get(
        f"/api/analysis-runs/{run_id}/neoantigen-candidates",
        params={"status": "RANKED"},
    ).json()
    assert ranked
    assert all(c["status"] == "RANKED" for c in ranked)

    searched = client.get(
        f"/api/analysis-runs/{run_id}/neoantigen-candidates",
        params={"search": "MOCKGENE1"},
    ).json()
    assert searched
    assert all("MOCKGENE1" in (c["gene"] or "") or "MOCKGENE1" in c["peptide_representation"] for c in searched)
