from app.validation.gold import EXPECTED, GOLD_DATASET_NAME


def _run(client):
    response = client.post("/api/validation/run")
    assert response.status_code == 200
    return response.json()


def test_full_validation_passes_on_gold_dataset(client):
    report = _run(client)

    assert report["status"] == "VALIDATED_SOFTWARE_BUILD"
    assert report["failed"] == 0
    assert report["passed"] > 0
    assert report["total_tests"] == report["passed"] + report["failed"] + report["warnings"]
    assert report["software_version"]
    assert "does not indicate" in (report["disclaimer"] or "").lower()

    stages = {entry["stage"]: entry["status"] for entry in report["pipeline_health"]}
    for stage in ("VCF_QC", "SOMATIC", "ANNOTATION", "HLA", "EXPRESSION", "CANDIDATE", "PREDICTION", "RANKING", "CONSTRUCT"):
        assert stages.get(stage) == "PASS", (stage, stages.get(stage))


def test_every_case_has_expected_actual_and_no_silent_status(client):
    report = _run(client)
    assert report["cases"]
    for case in report["cases"]:
        assert case["status"] in ("PASS", "FAIL", "WARNING")
        assert "expected_result" in case
        assert "actual_result" in case


def test_validation_categories_present(client):
    report = _run(client)
    categories = {case["category"] for case in report["cases"]}
    assert {
        "INPUT_VALIDATION",
        "BIOLOGICAL_DATA_INTEGRATION",
        "PIPELINE_VALIDATION",
        "PROVENANCE_VALIDATION",
        "REPRODUCIBILITY",
        "CONSTRUCT_VALIDATION",
    } <= categories

    summary = report["category_summary"]
    assert summary["INPUT_VALIDATION"]["total"] >= 4
    assert summary["REPRODUCIBILITY"]["passed"] == summary["REPRODUCIBILITY"]["total"]


def test_input_validation_detects_bad_input(client):
    report = _run(client)
    names = {case["name"] for case in report["cases"] if case["category"] == "INPUT_VALIDATION"}
    assert "Malformed VCF record detected" in names
    assert "Missing required field detected" in names
    assert "Invalid allele detected" in names
    assert "Reference build mismatch rejected" in names
    for case in report["cases"]:
        if case["category"] == "INPUT_VALIDATION":
            assert case["status"] == "PASS"


def test_expected_scientific_results_match(client):
    report = _run(client)
    by_name = {case["name"]: case for case in report["cases"]}

    assert by_name["Annotation mapping"]["actual_result"] == EXPECTED["annotation"]
    assert by_name["Tumor/normal classification"]["actual_result"] == EXPECTED["somatic"]
    assert by_name["HLA normalization"]["actual_result"]["valid"] == 6
    assert by_name["Candidate generation"]["actual_result"] == {
        "total": EXPECTED["neoantigen"]["total"],
        "generated": EXPECTED["neoantigen"]["generated"],
        "rejected": EXPECTED["neoantigen"]["rejected"],
    }
    assert by_name["Construct representation"]["actual_result"] == EXPECTED["construct"]["representation"]
    assert by_name["Ranking status"]["actual_result"] == {"ranked": EXPECTED["neoantigen"]["ranked"]}


def test_provenance_and_reproducibility(client):
    report = _run(client)

    assert report["reproducibility"]["deterministic"] is True
    assert report["reproducibility"]["status"] == "PASS"
    assert report["reproducibility"]["random_seed"] is None

    prov = [case for case in report["cases"] if case["category"] == "PROVENANCE_VALIDATION"]
    assert prov
    assert all(case["status"] == "PASS" for case in prov)

    repro = [case for case in report["cases"] if case["category"] == "REPRODUCIBILITY"]
    assert {case["step"] for case in repro} >= {"CANDIDATE", "PREDICTION", "RANKING", "CONSTRUCT"}


def test_audit_log_recorded(client):
    report = _run(client)
    logs = report["audit_logs"]
    assert logs
    steps = {log["step"] for log in logs}
    assert {"analysis", "annotation", "neoantigen_engine", "construct", "reproducibility"} <= steps
    for log in logs:
        assert log["status"]
        assert "timestamp" in log


def test_reports_and_datasets_listing(client):
    report = _run(client)

    reports = client.get("/api/validation/reports").json()
    assert any(item["id"] == report["id"] for item in reports)

    detail = client.get(f"/api/validation/reports/{report['id']}").json()
    assert detail["id"] == report["id"]
    assert detail["cases"]

    datasets = client.get("/api/validation/datasets").json()
    assert any(dataset["name"] == GOLD_DATASET_NAME for dataset in datasets)
