"""Tests for the project module: patient registration files, notes, reminders
and the HLA / expression analyze actions."""
from __future__ import annotations

import io

import pytest


def _project(client, name="Module Project", patient="患者一"):
    return client.post(
        "/api/projects", json={"name": name, "patient_name": patient}
    ).json()


def test_project_patient_name_roundtrip(client):
    project = _project(client)
    assert project["patient_name"] == "患者一"
    fetched = client.get(f"/api/projects/{project['id']}").json()
    assert fetched["patient_name"] == "患者一"


# ---- project files -----------------------------------------------------------


def test_project_file_upload_list_download_delete(client):
    project = _project(client)
    response = client.post(
        f"/api/projects/{project['id']}/files",
        files={"file": ("tumor.vcf", io.BytesIO(b"##fileformat=VCFv4.2\n"), "text/plain")},
        data={"kind": "TUMOR_VCF"},
    )
    assert response.status_code == 201
    uploaded = response.json()
    assert uploaded["kind"] == "TUMOR_VCF"
    assert uploaded["file_size_bytes"] == len(b"##fileformat=VCFv4.2\n")
    assert uploaded["input_hash"]

    rows = client.get(f"/api/projects/{project['id']}/files").json()
    assert len(rows) == 1 and rows[0]["id"] == uploaded["id"]

    download = client.get(f"/api/projects/{project['id']}/files/{uploaded['id']}")
    assert download.status_code == 200
    assert download.content.startswith(b"##fileformat")

    assert (
        client.delete(f"/api/projects/{project['id']}/files/{uploaded['id']}").status_code
        == 204
    )
    assert client.get(f"/api/projects/{project['id']}/files").json() == []


def test_project_file_unsupported_kind_400(client):
    project = _project(client)
    response = client.post(
        f"/api/projects/{project['id']}/files",
        files={"file": ("x.txt", io.BytesIO(b"x"), "text/plain")},
        data={"kind": "NOPE"},
    )
    assert response.status_code == 400


def test_project_file_not_found(client):
    project = _project(client)
    assert client.get(f"/api/projects/{project['id']}/files/missing").status_code == 404


# ---- notes -------------------------------------------------------------------


def test_notes_crud(client):
    project = _project(client)
    created = client.post(
        f"/api/projects/{project['id']}/notes", json={"content": "第一批样本已收"}
    )
    assert created.status_code == 201
    note = created.json()
    assert note["content"] == "第一批样本已收"

    rows = client.get(f"/api/projects/{project['id']}/notes").json()
    assert len(rows) == 1

    updated = client.patch(
        f"/api/projects/{project['id']}/notes/{note['id']}",
        json={"content": "第一批样本已收（已质检）"},
    )
    assert updated.json()["content"] == "第一批样本已收（已质检）"

    assert (
        client.delete(f"/api/projects/{project['id']}/notes/{note['id']}").status_code
        == 204
    )
    assert client.get(f"/api/projects/{project['id']}/notes").json() == []


def test_note_empty_content_422(client):
    project = _project(client)
    assert (
        client.post(f"/api/projects/{project['id']}/notes", json={"content": ""}).status_code
        == 422
    )


# ---- reminders ---------------------------------------------------------------


def test_reminders_crud(client):
    project = _project(client)
    created = client.post(
        f"/api/projects/{project['id']}/reminders",
        json={"title": "复核 HLA 结果", "due_at": "2026-10-10T09:00:00Z"},
    )
    assert created.status_code == 201
    reminder = created.json()
    assert reminder["done"] is False

    rows = client.get(f"/api/projects/{project['id']}/reminders").json()
    assert len(rows) == 1

    updated = client.patch(
        f"/api/projects/{project['id']}/reminders/{reminder['id']}", json={"done": True}
    )
    assert updated.json()["done"] is True
    rows = client.get(f"/api/projects/{project['id']}/reminders").json()
    assert rows[0]["done"] is True

    assert (
        client.delete(
            f"/api/projects/{project['id']}/reminders/{reminder['id']}"
        ).status_code
        == 204
    )


def test_reminder_missing_title_422(client):
    project = _project(client)
    assert (
        client.post(
            f"/api/projects/{project['id']}/reminders", json={"title": ""}
        ).status_code
        == 422
    )


# ---- analyze actions ---------------------------------------------------------


def _ready_run(client, name):
    project_id = client.post("/api/projects", json={"name": name}).json()["id"]
    integration = client.post(f"/api/projects/{project_id}/synthetic-integration").json()
    return integration["analysis_run_id"]


def test_hla_analyze_action(client):
    run_id = _ready_run(client, "HLA Analyze")
    response = client.post(f"/api/analysis-runs/{run_id}/hla/analyze")
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "hla_analyzed"
    assert body["status"] == "HLA_AVAILABLE"
    assert isinstance(body["profiles"], list) and body["profiles"]
    profile = body["profiles"][0]
    assert set(profile) >= {"allele", "allele_class", "is_valid", "is_duplicate"}


def test_hla_analyze_when_empty(client):
    project_id = client.post("/api/projects", json={"name": "HLA Empty"}).json()["id"]
    run = client.post(
        "/api/analysis-runs/synthetic", json={"project_id": project_id}
    ).json()
    body = client.post(f"/api/analysis-runs/{run['id']}/hla/analyze").json()
    assert body["status"] == "HLA_UNAVAILABLE"
    assert body["profiles"] == []


def test_expression_analyze_action(client):
    run_id = _ready_run(client, "Expr Analyze")
    response = client.post(f"/api/analysis-runs/{run_id}/expression/analyze")
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "expression_analyzed"
    assert body["status"] == "EXPRESSION_AVAILABLE"
    assert body["top_expressed"]
    top = body["top_expressed"][0]
    assert "gene_symbol" in top and "expression_value" in top
