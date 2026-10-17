def _full_run(client, name="Report Project"):
    project_id = client.post("/api/projects", json={"name": name}).json()["id"]
    integration = client.post(f"/api/projects/{project_id}/synthetic-integration").json()
    run_id = integration["analysis_run_id"]
    client.post(f"/api/analysis-runs/{run_id}/neoantigen/run", json={"provider": "mock"})
    candidates = client.get(
        f"/api/analysis-runs/{run_id}/neoantigen-candidates",
        params={"status": "RANKED"},
    ).json()
    client.post(
        f"/api/analysis-runs/{run_id}/constructs",
        json={"candidate_ids": [c["id"] for c in candidates[:2]]},
    )
    return project_id, run_id


def test_generate_and_list_report(client):
    project_id, run_id = _full_run(client)

    response = client.post(
        f"/api/analysis-runs/{run_id}/reports",
        json={"format": "markdown", "generated_by": "researcher@lab"},
    )
    assert response.status_code == 201
    report = response.json()
    assert report["format"] == "markdown"
    assert report["status"] == "GENERATED"
    assert report["generated_by"] == "researcher@lab"
    assert report["summary"]["candidate_count"] > 0
    assert report["summary"]["construct_count"] >= 1
    assert "Neoantigen Analysis Report" in report["content"]
    assert "research use only" in report["content"]

    listed = client.get("/api/reports", params={"analysis_run_id": run_id}).json()
    assert len(listed) == 1
    assert listed[0]["id"] == report["id"]

    detail = client.get(f"/api/reports/{report['id']}").json()
    assert detail["content"] == report["content"]


def test_report_download(client):
    _, run_id = _full_run(client, "Download Project")
    report = client.post(
        f"/api/analysis-runs/{run_id}/reports", json={"format": "html"}
    ).json()

    download = client.get(f"/api/reports/{report['id']}/download")
    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]
    assert "<!doctype html>" in download.text


def test_direct_run_report_formats(client):
    _, run_id = _full_run(client, "Direct Project")

    as_json = client.get(
        f"/api/analysis-runs/{run_id}/report", params={"format": "json"}
    )
    assert as_json.status_code == 200
    payload = as_json.json()
    assert payload["neoantigen_candidates"]
    assert payload["disclaimer"]
    assert payload["analysis_run"]["id"] == run_id

    as_csv = client.get(
        f"/api/analysis-runs/{run_id}/report", params={"format": "csv"}
    )
    assert as_csv.status_code == 200
    assert "candidate_id,gene,protein_change" in as_csv.text

    as_html = client.get(
        f"/api/analysis-runs/{run_id}/report", params={"format": "html"}
    )
    assert as_html.status_code == 200
    assert "research use only" in as_html.text


def test_report_pdf_output(client):
    _, run_id = _full_run(client, "PDF Project")

    direct = client.get(
        f"/api/analysis-runs/{run_id}/report", params={"format": "pdf"}
    )
    assert direct.status_code == 200
    assert direct.headers["content-type"] == "application/pdf"
    assert direct.content[:5] == b"%PDF-"

    report = client.post(
        f"/api/analysis-runs/{run_id}/reports", json={"format": "pdf"}
    ).json()
    assert report["format"] == "pdf"

    download = client.get(f"/api/reports/{report['id']}/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.content[:5] == b"%PDF-"


def test_report_format_validation(client):
    project_id = client.post("/api/projects", json={"name": "Bad Format"}).json()["id"]
    run = client.post(
        "/api/analysis-runs/synthetic", json={"project_id": project_id}
    ).json()

    response = client.post(
        f"/api/analysis-runs/{run['id']}/reports", json={"format": "xml"}
    )
    assert response.status_code == 400


def test_report_rows_are_capped_and_pdf_renders(client, monkeypatch):
    """Large runs must not produce unbounded reports: detailed rows are capped
    (with totals kept) and every format, including PDF, still renders."""
    from app.services import report_service

    project_id, run_id = _full_run(client, "Report cap")
    monkeypatch.setattr(report_service, "MAX_REPORT_ROWS", 1)

    body = client.get(
        f"/api/analysis-runs/{run_id}/report", params={"format": "json"}
    ).json()
    limits = body["limits"]
    assert limits["max_rows"] == 1
    assert len(body["annotations"]) <= 1
    assert len(body["somatic_candidates"]) <= 1
    # Totals still reflect the full dataset -> truncation is reported, not hidden.
    assert limits["annotations_total"] >= len(body["annotations"])
    assert limits["truncated"] is True

    for fmt in ("markdown", "html", "csv", "pdf"):
        response = client.get(
            f"/api/analysis-runs/{run_id}/report", params={"format": fmt}
        )
        assert response.status_code == 200, fmt
    assert client.get(
        f"/api/analysis-runs/{run_id}/report", params={"format": "pdf"}
    ).content.startswith(b"%PDF")
