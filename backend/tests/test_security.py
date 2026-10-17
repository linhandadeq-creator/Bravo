from app.core.config import settings


def test_auth_disabled_by_default(client):
    # No token configured -> open access.
    assert client.get("/api/projects").status_code == 200


def test_auth_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "API_TOKEN", "s3cret")
    assert client.get("/api/projects").status_code == 401
    assert (
        client.get("/api/projects", headers={"X-API-Key": "wrong"}).status_code == 401
    )
    ok = client.get("/api/projects", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
    # Health stays open.
    assert client.get("/api/health").status_code == 200


def test_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)
    assert client.get("/api/projects").status_code == 200
    assert client.get("/api/projects").status_code == 200
    assert client.get("/api/projects").status_code == 429


def test_delete_project_cascades(client):
    project_id = client.post("/api/projects", json={"name": "Delete me"}).json()["id"]
    run_id = client.post(
        f"/api/projects/{project_id}/synthetic-integration"
    ).json()["analysis_run_id"]
    assert client.get(f"/api/analysis-runs/{run_id}").status_code == 200

    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    # Child analysis run must be gone (ON DELETE CASCADE now enforced).
    assert client.get(f"/api/analysis-runs/{run_id}").status_code == 404
