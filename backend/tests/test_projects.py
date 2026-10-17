def test_list_projects_empty(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert response.json() == []


def test_create_project(client):
    payload = {
        "name": "Demo Cancer Project",
        "description": "Demo",
        "status": "active",
    }
    response = client.post("/api/projects", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Demo Cancer Project"
    assert body["id"]
    assert body["created_at"]
    assert body["updated_at"]


def test_get_project(client):
    created = client.post("/api/projects", json={"name": "P1"}).json()
    response = client.get(f"/api/projects/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_project_not_found(client):
    response = client.get("/api/projects/does-not-exist")
    assert response.status_code == 404


def test_update_project(client):
    created = client.post("/api/projects", json={"name": "P1"}).json()
    response = client.patch(f"/api/projects/{created['id']}", json={"status": "archived"})
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_project_case_information_roundtrip(client):
    created = client.post(
        "/api/projects",
        json={
            "name": "病例信息项目",
            "patient_name": "合成患者",
            "age": 58,
            "sex": "F",
            "cancer_type": "Lung adenocarcinoma",
            "stage": "IIIB",
            "diagnosis": "Synthetic case for parser/UI testing",
        },
    ).json()
    assert created["age"] == 58
    assert created["cancer_type"] == "Lung adenocarcinoma"

    updated = client.patch(
        f"/api/projects/{created['id']}", json={"stage": "IV", "age": 59}
    ).json()
    assert updated["stage"] == "IV"
    assert updated["age"] == 59

    fetched = client.get(f"/api/projects/{created['id']}").json()
    assert fetched["sex"] == "F"
    assert fetched["diagnosis"].startswith("Synthetic")
