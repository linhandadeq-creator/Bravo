def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_docs_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/health" in response.json()["paths"]
