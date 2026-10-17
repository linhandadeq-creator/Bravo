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


def _checks(construct):
    return {check["id"]: check["status"] for check in construct["qc_summary"]["checks"]}


def test_valid_simulation_construct_and_representation(client):
    _, run_id = _ready_run(client, "Construct Project")
    ranked = _candidates(client, run_id, {"status": "RANKED"})
    ids = [c["id"] for c in ranked[:3]]
    assert len(ids) == 3

    response = client.post(
        f"/api/analysis-runs/{run_id}/constructs",
        json={"candidate_ids": ids, "selected_by": "researcher@lab"},
    )
    assert response.status_code == 201
    construct = response.json()

    assert construct["status"] == "VALIDATED_SIMULATION"
    assert construct["construct_representation"] == (
        "[5PRIME] [ANTIGEN_001] [SPACER] [ANTIGEN_002] [SPACER] [ANTIGEN_003] [3PRIME]"
    )
    assert [item["label"] for item in construct["items"]] == [
        "ANTIGEN_001",
        "ANTIGEN_002",
        "ANTIGEN_003",
    ]
    assert [item["position"] for item in construct["items"]] == [1, 2, 3]
    assert construct["items"][0]["selected_by"] == "researcher@lab"
    assert construct["selected_at"]
    assert construct["candidate_version"]
    assert construct["sequence"]
    assert construct["simulation_output"]["simulation"] is True
    assert construct["simulation_output"]["not_for_clinical_use"] is True
    assert set(construct["simulation_output"]["sections"]) == {
        "human_dosing_regimen",
        "clinical_treatment_protocol",
        "laboratory_manufacturing_sop",
        "manufacturing_parameters",
        "release_criteria",
        "actual_production_formulation",
        "production_instructions",
    }


def test_duplicate_detection(client):
    _, run_id = _ready_run(client, "Duplicate Project")
    ranked = _candidates(client, run_id, {"status": "RANKED"})
    duplicate = ranked[0]["id"]

    construct = client.post(
        f"/api/analysis-runs/{run_id}/constructs",
        json={"candidate_ids": [duplicate, duplicate]},
    ).json()
    assert construct["status"] == "INVALID"
    assert _checks(construct)["duplicate_candidates"] == "fail"


def test_missing_candidate(client):
    _, run_id = _ready_run(client, "Missing Project")
    construct = client.post(
        f"/api/analysis-runs/{run_id}/constructs",
        json={"candidate_ids": ["does-not-exist"], "selected_by": "x"},
    ).json()
    assert construct["status"] == "INVALID"
    assert _checks(construct)["candidate_exists"] == "fail"


def test_candidate_from_other_run_is_invalid(client):
    _, run_a = _ready_run(client, "Run A Project")
    _, run_b = _ready_run(client, "Run B Project")
    foreign = _candidates(client, run_b, {"status": "RANKED"})[0]["id"]

    construct = client.post(
        f"/api/analysis-runs/{run_a}/constructs",
        json={"candidate_ids": [foreign]},
    ).json()
    assert construct["status"] == "INVALID"
    assert _checks(construct)["same_analysis_run"] == "fail"


def test_unranked_candidate_is_invalid(client):
    _, run_id = _ready_run(client, "Unranked Project", provider="external")
    candidates = _candidates(client, run_id)
    assert candidates

    construct = client.post(
        f"/api/analysis-runs/{run_id}/constructs",
        json={"candidate_ids": [candidates[0]["id"]]},
    ).json()
    assert construct["status"] == "INVALID"
    checks = _checks(construct)
    assert checks["prediction_status"] == "fail"
    assert checks["ranking_status"] == "fail"


def test_reorder_updates_ordering(client):
    _, run_id = _ready_run(client, "Reorder Project")
    ranked = _candidates(client, run_id, {"status": "RANKED"})
    ids = [c["id"] for c in ranked[:3]]

    construct = client.post(
        f"/api/analysis-runs/{run_id}/constructs", json={"candidate_ids": ids}
    ).json()
    reordered = client.put(
        f"/api/constructs/{construct['id']}/selection",
        json={"candidate_ids": [ids[2], ids[0], ids[1]], "selected_by": "editor"},
    ).json()

    assert reordered["candidate_ids"] == [ids[2], ids[0], ids[1]]
    assert [item["candidate_id"] for item in reordered["items"]] == [ids[2], ids[0], ids[1]]
    assert [item["label"] for item in reordered["items"]] == [
        "ANTIGEN_001",
        "ANTIGEN_002",
        "ANTIGEN_003",
    ]


def test_traceability_chain(client):
    _, run_id = _ready_run(client, "Trace Project")
    ranked = _candidates(client, run_id, {"status": "RANKED"})
    construct = client.post(
        f"/api/analysis-runs/{run_id}/constructs",
        json={"candidate_ids": [ranked[0]["id"]]},
    ).json()

    trace = construct["qc_summary"]["traceability"][0]
    assert trace["ok"] is True
    steps = [step["step"] for step in trace["steps"]]
    assert steps == ["candidate", "variant", "annotation", "hla", "prediction", "ranking"]
    assert all(step["ok"] for step in trace["steps"])


def test_empty_construct_is_draft_then_invalid_on_validate(client):
    _, run_id = _ready_run(client, "Draft Project")
    construct = client.post(
        f"/api/analysis-runs/{run_id}/constructs", json={"candidate_ids": []}
    ).json()
    assert construct["status"] == "DRAFT"

    validated = client.post(f"/api/constructs/{construct['id']}/validate").json()
    assert validated["status"] == "INVALID"


def test_lock_prevents_edits(client):
    _, run_id = _ready_run(client, "Lock Project")
    ranked = _candidates(client, run_id, {"status": "RANKED"})
    ids = [c["id"] for c in ranked[:2]]
    construct = client.post(
        f"/api/analysis-runs/{run_id}/constructs", json={"candidate_ids": ids}
    ).json()

    locked = client.post(f"/api/constructs/{construct['id']}/lock").json()
    assert locked["status"] == "LOCKED"

    blocked = client.put(
        f"/api/constructs/{construct['id']}/selection",
        json={"candidate_ids": [ids[0]]},
    )
    assert blocked.status_code == 409


def test_export_formats(client):
    _, run_id = _ready_run(client, "Export Project")
    ranked = _candidates(client, run_id, {"status": "RANKED"})
    construct = client.post(
        f"/api/analysis-runs/{run_id}/constructs",
        json={"candidate_ids": [c["id"] for c in ranked[:2]]},
    ).json()
    cid = construct["id"]

    json_export = client.get(f"/api/constructs/{cid}/export", params={"format": "json"})
    assert json_export.status_code == 200
    assert json_export.headers["content-type"].startswith("application/json")
    assert "RESEARCH SIMULATION" in json_export.text
    assert "production_package" in json_export.text

    csv_export = client.get(f"/api/constructs/{cid}/export", params={"format": "csv"})
    assert csv_export.status_code == 200
    assert "position,label,candidate_id" in csv_export.text
    assert "ANTIGEN_001" in csv_export.text

    report = client.get(f"/api/constructs/{cid}/export", params={"format": "report"})
    assert report.status_code == 200
    assert "mRNA Construct Research Report" in report.text
    assert "SIMULATION" in report.text
    assert "Antigen ordering" in report.text
