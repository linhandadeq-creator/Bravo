"""Tests for the database inspection / selective deletion feature."""
from __future__ import annotations


def test_database_overview(client):
    body = client.get("/api/database/overview").json()
    assert body["table_count"] > 0
    assert body["total_rows"] >= 0
    assert "database_file" in body


def test_database_tables_listing(client):
    tables = client.get("/api/database/tables").json()
    names = {t["name"] for t in tables}
    assert {"projects", "samples", "variants", "analysis_runs"} <= names
    assert all(isinstance(t["rows"], int) for t in tables)


def test_database_table_rows_and_pagination(client):
    project = client.post("/api/projects", json={"name": "DB view"}).json()
    body = client.get("/api/database/tables/projects", params={"limit": 10}).json()
    assert body["name"] == "projects"
    assert "id" in body["columns"]
    assert body["primary_key"] == ["id"]
    assert body["total"] >= 1
    assert any(row["id"] == project["id"] for row in body["rows"])

    limited = client.get("/api/database/tables/projects", params={"limit": 1, "offset": 0}).json()
    assert len(limited["rows"]) == 1


def test_database_unknown_table_404(client):
    assert client.get("/api/database/tables/nope").status_code == 404


def test_delete_rows_removes_selected_only(client):
    keep = client.post("/api/projects", json={"name": "keep"}).json()
    drop = client.post("/api/projects", json={"name": "drop"}).json()

    response = client.post(
        "/api/database/tables/projects/delete", json={"ids": [drop["id"]]}
    )
    assert response.status_code == 200
    assert response.json()["deleted"] == 1

    remaining = {row["id"] for row in client.get("/api/database/tables/projects").json()["rows"]}
    assert keep["id"] in remaining
    assert drop["id"] not in remaining


def test_delete_empty_selection_400(client):
    response = client.post("/api/database/tables/projects/delete", json={"ids": []})
    assert response.status_code == 400


def test_delete_unknown_table_404(client):
    response = client.post(
        "/api/database/tables/nope/delete", json={"ids": ["x"]}
    )
    assert response.status_code == 404


def test_clear_table(client):
    project = client.post("/api/projects", json={"name": "to clear"}).json()
    assert project["id"]
    response = client.post("/api/database/tables/project_reminders/clear")
    assert response.status_code == 200
    assert response.json()["deleted"] == 0


def test_delete_project_cascades_children(client, annotation_dataset):
    project = client.post("/api/projects", json={"name": "cascade"}).json()
    with open(annotation_dataset["tumor"], "rb") as tumor, open(
        annotation_dataset["normal"], "rb"
    ) as normal:
        run = client.post(
            "/api/analysis-runs/upload",
            data={"project_id": project["id"], "reference_build": "GRCh38"},
            files={
                "tumor_file": ("tumor.vcf", tumor, "text/plain"),
                "normal_file": ("normal.vcf", normal, "text/plain"),
            },
        ).json()
    assert run["id"]

    # Deleting the project row cascades to samples/runs/variants (FK cascade).
    client.post("/api/database/tables/projects/delete", json={"ids": [project["id"]]})
    samples = client.get(
        "/api/database/tables/samples", params={"limit": 200}
    ).json()
    assert all(row["project_id"] != project["id"] for row in samples["rows"])
