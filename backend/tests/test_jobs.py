import pytest

from app.services import jobs


def test_job_registry_state_machine():
    job = jobs.create_job()
    assert job.status == jobs.QUEUED
    job.emit("VCF_QC", "PASS")
    assert job.to_dict()["stages"][0]["step"] == "VCF_QC"
    jobs.request_cancel(job.id)
    assert jobs.get_job(job.id).cancel_requested is True


def test_execute_one_click_reports_progress(session):
    from app.services.one_click import OneClickParams, execute_one_click

    stages: list[tuple[str, str]] = []
    result = execute_one_click(
        session,
        OneClickParams(demo=True, top_n=3),
        progress=lambda step, status, detail: stages.append((step, status)),
    )
    assert result.status == "SUCCESS"
    assert any(step == "NEOANTIGEN" for step, _ in stages)
    assert any(step == "REPORT" for step, _ in stages)


def test_execute_one_click_honours_cancel(session):
    from app.services.one_click import (
        CancelledError,
        OneClickParams,
        execute_one_click,
    )

    with pytest.raises(CancelledError):
        execute_one_click(session, OneClickParams(demo=True), cancel=lambda: True)


def test_one_click_async_job_endpoint(client, monkeypatch):
    # Run the worker inline so the test is deterministic (no thread/DB race).
    monkeypatch.setattr(jobs, "submit", lambda job, worker: worker(job))
    response = client.post(
        "/api/one-click/jobs", data={"demo": "true", "top_n": "3"}
    )
    assert response.status_code == 201
    job_id = response.json()["id"]

    job = client.get(f"/api/one-click/jobs/{job_id}").json()
    assert job["status"] == "SUCCESS", job
    assert job["result"]["construct_id"]
    assert any(stage["step"] == "NEOANTIGEN" for stage in job["stages"])
