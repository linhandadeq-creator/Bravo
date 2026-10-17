"""One-click user module: upload files → automatic mRNA blueprint.

Synchronous endpoint (``/one-click/generate``) plus an asynchronous job API
(``/one-click/jobs``) that runs the same pipeline in the background with live
stage progress and cancellation.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.reference import DEFAULT_REFERENCE_BUILD
from app.db import session as db_session
from app.db.session import get_db
from app.schemas.generate import OneClickResult
from app.services import jobs
from app.services.blueprint_service import (
    blueprint_pdf,
    blueprint_svg,
    build_blueprint,
    build_blueprint_html,
)
from app.services.construct_service import ConstructError, get_construct
from app.services.one_click import (
    CancelledError,
    OneClickParams,
    OneClickUploads,
    execute_one_click,
    infer_format,
)
from app.services.uploads import copy_limited, read_text_limited

router = APIRouter(tags=["one-click"])


def _params(
    project_name: str,
    project_id: str | None,
    reference_build: str,
    provider: str,
    annotation_provider: str,
    top_n: int,
    simulation_format: str,
    use_synthetic_context: bool,
    demo: bool,
) -> OneClickParams:
    return OneClickParams(
        project_name=project_name,
        project_id=project_id or None,
        reference_build=reference_build,
        provider=provider,
        annotation_provider=annotation_provider,
        top_n=top_n,
        simulation_format=simulation_format,
        use_synthetic_context=use_synthetic_context,
        demo=demo,
    )


@router.post("/one-click/generate", response_model=OneClickResult)
def one_click_generate(
    tumor_file: UploadFile | None = File(default=None),
    normal_file: UploadFile | None = File(default=None),
    hla_file: UploadFile | None = File(default=None),
    expression_file: UploadFile | None = File(default=None),
    project_name: str = Form(default="One-Click Project"),
    project_id: str | None = Form(default=None),
    reference_build: str = Form(default=DEFAULT_REFERENCE_BUILD),
    provider: str = Form(default="mock"),
    annotation_provider: str = Form(default="mock"),
    top_n: int = Form(default=5),
    simulation_format: str = Form(default="mRNA-LNP"),
    use_synthetic_context: bool = Form(default=False),
    demo: bool = Form(default=False),
    db: Session = Depends(get_db),
) -> OneClickResult:
    uploads = OneClickUploads(
        tumor=tumor_file.file if tumor_file and tumor_file.filename else None,
        tumor_name=tumor_file.filename if tumor_file else None,
        normal=normal_file.file if normal_file and normal_file.filename else None,
        normal_name=normal_file.filename if normal_file else None,
        hla_text=read_text_limited(hla_file.file)
        if hla_file and hla_file.filename
        else None,
        hla_format=infer_format(hla_file.filename, None) if hla_file and hla_file.filename else "json",
        expression_text=read_text_limited(expression_file.file)
        if expression_file and expression_file.filename
        else None,
        expression_format=infer_format(expression_file.filename, None)
        if expression_file and expression_file.filename
        else "tsv",
    )
    params = _params(
        project_name,
        project_id,
        reference_build,
        provider,
        annotation_provider,
        top_n,
        simulation_format,
        use_synthetic_context,
        demo,
    )
    try:
        return execute_one_click(db, params, uploads)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---- asynchronous job API ---------------------------------------------------


@router.post("/one-click/jobs", status_code=201)
def create_one_click_job(
    tumor_file: UploadFile | None = File(default=None),
    normal_file: UploadFile | None = File(default=None),
    hla_file: UploadFile | None = File(default=None),
    expression_file: UploadFile | None = File(default=None),
    project_name: str = Form(default="One-Click Project"),
    project_id: str | None = Form(default=None),
    reference_build: str = Form(default=DEFAULT_REFERENCE_BUILD),
    provider: str = Form(default="mock"),
    annotation_provider: str = Form(default="mock"),
    top_n: int = Form(default=5),
    simulation_format: str = Form(default="mRNA-LNP"),
    use_synthetic_context: bool = Form(default=False),
    demo: bool = Form(default=False),
) -> dict:
    job = jobs.create_job()
    job_dir = settings.storage_path / "jobs" / job.id
    job_dir.mkdir(parents=True, exist_ok=True)

    payload: dict = {
        "project_name": project_name,
        "project_id": project_id or None,
        "reference_build": reference_build,
        "provider": provider,
        "annotation_provider": annotation_provider,
        "top_n": top_n,
        "simulation_format": simulation_format,
        "use_synthetic_context": use_synthetic_context,
        "demo": demo,
    }

    tumor_path = normal_path = None
    if tumor_file is not None and tumor_file.filename:
        tumor_path = job_dir / "tumor.vcf"
        copy_limited(tumor_file.file, tumor_path)
        payload["tumor_name"] = tumor_file.filename
    if normal_file is not None and normal_file.filename:
        normal_path = job_dir / "normal.vcf"
        copy_limited(normal_file.file, normal_path)
        payload["normal_name"] = normal_file.filename
    if hla_file is not None and hla_file.filename:
        payload["hla_text"] = read_text_limited(hla_file.file)
        payload["hla_format"] = infer_format(hla_file.filename, None)
    if expression_file is not None and expression_file.filename:
        payload["expression_text"] = read_text_limited(expression_file.file)
        payload["expression_format"] = infer_format(expression_file.filename, None)
    payload["tumor_path"] = str(tumor_path) if tumor_path else None
    payload["normal_path"] = str(normal_path) if normal_path else None

    def worker(current: jobs.Job) -> None:
        db = db_session.SessionLocal()
        handles = []
        try:
            uploads = OneClickUploads(
                hla_text=payload.get("hla_text"),
                hla_format=payload.get("hla_format", "json"),
                expression_text=payload.get("expression_text"),
                expression_format=payload.get("expression_format", "tsv"),
            )
            if payload.get("tumor_path"):
                handle = open(payload["tumor_path"], "rb")
                handles.append(handle)
                uploads.tumor = handle
                uploads.tumor_name = payload.get("tumor_name")
            if payload.get("normal_path"):
                handle = open(payload["normal_path"], "rb")
                handles.append(handle)
                uploads.normal = handle
                uploads.normal_name = payload.get("normal_name")

            params = OneClickParams(
                project_name=payload["project_name"],
                project_id=payload.get("project_id"),
                reference_build=payload["reference_build"],
                provider=payload["provider"],
                annotation_provider=payload["annotation_provider"],
                top_n=payload["top_n"],
                simulation_format=payload["simulation_format"],
                use_synthetic_context=payload["use_synthetic_context"],
                demo=payload["demo"],
            )
            result = execute_one_click(
                db,
                params,
                uploads,
                progress=current.emit,
                cancel=lambda: current.cancel_requested,
            )
            with current._lock:
                current.result = result.model_dump()
                current.status = result.status  # SUCCESS or BLOCKED
        except CancelledError:
            with current._lock:
                current.status = jobs.CANCELLED
        finally:
            for handle in handles:
                try:
                    handle.close()
                except Exception:  # noqa: BLE001
                    pass
            db.close()

    jobs.submit(job, worker)
    return job.to_dict()


@router.get("/one-click/jobs/{job_id}")
def get_one_click_job(job_id: str) -> dict:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@router.post("/one-click/jobs/{job_id}/cancel")
def cancel_one_click_job(job_id: str) -> dict:
    job = jobs.request_cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


# ---- blueprint rendering ----------------------------------------------------


@router.get("/constructs/{construct_id}/blueprint")
def get_blueprint(
    construct_id: str,
    format: str = Query(default="json", pattern="^(json|svg|html|pdf)$"),
    db: Session = Depends(get_db),
):
    try:
        construct = get_construct(db, construct_id)
    except ConstructError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    blueprint = build_blueprint(db, construct)
    if format == "svg":
        return Response(content=blueprint_svg(blueprint["segments"]), media_type="image/svg+xml")
    if format == "html":
        return Response(content=build_blueprint_html(blueprint), media_type="text/html")
    if format == "pdf":
        return Response(
            content=blueprint_pdf(blueprint),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="blueprint_{construct_id[:8]}.pdf"'},
        )
    return blueprint
