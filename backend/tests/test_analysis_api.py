from app.services.synthetic import EXPECTED_SYNTHETIC


def _create_project(client, name="Demo Cancer Project") -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def test_synthetic_run_end_to_end(client):
    project_id = _create_project(client)

    response = client.post(
        "/api/analysis-runs/synthetic", json={"project_id": project_id}
    )
    assert response.status_code == 201
    run = response.json()

    assert run["status"] == "PASS"
    assert run["reference_build"] == EXPECTED_SYNTHETIC["reference_build"]
    assert run["mode"] == "SYNTHETIC"
    assert run["tumor_sample_id"] and run["normal_sample_id"]

    qc = run["qc_summary"]
    assert qc["tumor"]["raw_variants"] == EXPECTED_SYNTHETIC["tumor"]["raw_variants"]
    assert qc["tumor"]["invalid_variants"] == EXPECTED_SYNTHETIC["tumor"]["invalid_variants"]
    assert qc["duplicate_variants"] == EXPECTED_SYNTHETIC["tumor"]["duplicate_variants"]
    assert qc["chromosome_normalizations"] >= 1
    assert run["somatic_summary"] == EXPECTED_SYNTHETIC["somatic"]

    variants = client.get(
        f"/api/analysis-runs/{run['id']}/variants",
        params={"valid_only": "true", "include_duplicates": "false"},
    ).json()
    expected_unique = (
        EXPECTED_SYNTHETIC["tumor"]["unique_variants"]
        + EXPECTED_SYNTHETIC["normal"]["unique_variants"]
    )
    assert len(variants) == expected_unique

    candidates = client.get(
        f"/api/analysis-runs/{run['id']}/somatic-candidates"
    ).json()
    assert len(candidates) == sum(EXPECTED_SYNTHETIC["somatic"].values())

    listed = client.get(
        "/api/analysis-runs", params={"project_id": project_id}
    ).json()
    assert len(listed) == 1


def test_upload_without_normal_is_blocked(client, synthetic_dataset):
    project_id = _create_project(client, "Blocked Project")

    with open(synthetic_dataset.tumor_path, "rb") as tumor:
        response = client.post(
            "/api/analysis-runs/upload",
            data={"project_id": project_id, "reference_build": "GRCh38"},
            files={"tumor_file": ("tumor.vcf.gz", tumor, "application/gzip")},
        )

    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "BLOCKED"
    assert "Normal VCF is required" in run["error_message"]


def test_upload_reference_build_mismatch_fails(client, synthetic_dataset):
    project_id = _create_project(client, "Mismatch Project")

    with open(synthetic_dataset.tumor_path, "rb") as tumor, open(
        synthetic_dataset.normal_path, "rb"
    ) as normal:
        response = client.post(
            "/api/analysis-runs/upload",
            data={
                "project_id": project_id,
                "tumor_reference_build": "GRCh38",
                "normal_reference_build": "GRCh37",
            },
            files={
                "tumor_file": ("tumor.vcf.gz", tumor, "application/gzip"),
                "normal_file": ("normal.vcf", normal, "text/plain"),
            },
        )

    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "FAILED"
    assert "mismatch" in run["error_message"].lower()
    assert run["somatic_summary"] is None


def test_get_run_not_found(client):
    assert client.get("/api/analysis-runs/does-not-exist").status_code == 404
