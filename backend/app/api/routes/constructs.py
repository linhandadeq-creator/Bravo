import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blueprint.worklist import build_worklist, worklist_csv
from app.db.session import get_db
from app.models.neoantigen import NeoantigenCandidate, PredictionResult
from app.models.analysis_run import AnalysisRun
from app.models.construct import SimulationConstruct
from app.schemas.construct import ConstructCreate, ConstructRead, SelectionUpdate
from app.services.construct_service import (
    ConstructError,
    create_construct,
    export_construct,
    get_construct,
    list_constructs,
    lock_construct,
    update_selection,
    validate_construct,
)

router = APIRouter(tags=["constructs"])


def _get_run(db: Session, run_id: str) -> AnalysisRun:
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return run


def _get_or_404(db: Session, construct_id: str) -> SimulationConstruct:
    try:
        return get_construct(db, construct_id)
    except ConstructError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/analysis-runs/{run_id}/constructs",
    response_model=ConstructRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    run_id: str, payload: ConstructCreate, db: Session = Depends(get_db)
) -> SimulationConstruct:
    run = _get_run(db, run_id)
    return create_construct(
        db,
        run,
        payload.candidate_ids,
        payload.name,
        payload.simulation_format,
        payload.selected_by,
    )


@router.get(
    "/analysis-runs/{run_id}/constructs", response_model=list[ConstructRead]
)
def list_for_run(
    run_id: str, db: Session = Depends(get_db)
) -> list[SimulationConstruct]:
    _get_run(db, run_id)
    return list_constructs(db, run_id)


@router.get("/constructs/{construct_id}", response_model=ConstructRead)
def get(construct_id: str, db: Session = Depends(get_db)) -> SimulationConstruct:
    return _get_or_404(db, construct_id)


@router.put("/constructs/{construct_id}/selection", response_model=ConstructRead)
def set_selection(
    construct_id: str, payload: SelectionUpdate, db: Session = Depends(get_db)
) -> SimulationConstruct:
    construct = _get_or_404(db, construct_id)
    try:
        return update_selection(
            db, construct, payload.candidate_ids, payload.selected_by
        )
    except ConstructError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/constructs/{construct_id}/validate", response_model=ConstructRead)
def validate(construct_id: str, db: Session = Depends(get_db)) -> SimulationConstruct:
    construct = _get_or_404(db, construct_id)
    return validate_construct(db, construct)


@router.post("/constructs/{construct_id}/lock", response_model=ConstructRead)
def lock(construct_id: str, db: Session = Depends(get_db)) -> SimulationConstruct:
    construct = _get_or_404(db, construct_id)
    try:
        return lock_construct(db, construct)
    except ConstructError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _package_markdown(package: dict) -> str:
    qc = package.get("sequence_qc") or {}
    metrics = qc.get("metrics") or {}
    design = package.get("sequence_design") or {}
    manufacturing = package.get("manufacturing") or {}
    lines = [
        "# Production Blueprint Package",
        "",
        f"> {package.get('disclaimer', '')}",
        "",
        f"- Production-ready (in-silico): {'yes' if package.get('production_ready') else 'no'}",
        f"- Sequence QC status: {qc.get('status')} (manufacturability score {qc.get('manufacturability_score')})",
        f"- Sequence length: {design.get('dna_length')} nt (RNA {design.get('rna_length')} nt)",
        f"- GC: {metrics.get('gc_percent')}% · CAI: {metrics.get('cai')} · "
        f"Longest homopolymer: {metrics.get('longest_homopolymer')} · poly(A): {metrics.get('poly_a_length')} nt",
        f"- Restriction sites: {metrics.get('restriction_sites') or 'none'} · "
        f"Cryptic poly(A) signals: {metrics.get('polya_signals') or 'none'}",
        "",
        "## Components",
        "",
        "| Name | Type | Start | End | Length |",
        "| --- | --- | --- | --- | --- |",
    ]
    for region in design.get("regions", []):
        lines.append(
            f"| {region['name']} | {region['type']} | {region['start']} | "
            f"{region['end']} | {region['length']} |"
        )
    lines += ["", "## Manufacturing", "", "```json", json.dumps(manufacturing, ensure_ascii=False, indent=2), "```"]
    lines += [
        "",
        "## Release criteria (templates; confirm experimentally)",
        "",
        "```json",
        json.dumps(package.get("release_criteria_derived") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## QC checks",
        "",
    ]
    for check in qc.get("checks", []):
        lines.append(f"- [{check['status']}] {check['label']}: {check['detail']}")
    return "\n".join(lines)


@router.get("/constructs/{construct_id}/production-package")
def production_package(
    construct_id: str,
    format: str = Query(default="json", pattern="^(json|markdown)$"),
    db: Session = Depends(get_db),
):
    construct = _get_or_404(db, construct_id)
    package = construct.simulation_output or {}
    if format == "markdown":
        return Response(
            content=_package_markdown(package),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="blueprint_{construct_id[:8]}.md"'},
        )
    return package


@router.get("/constructs/{construct_id}/worklist")
def worklist(construct_id: str, db: Session = Depends(get_db)) -> Response:
    construct = _get_or_404(db, construct_id)
    candidate_ids = list(construct.candidate_ids or [])
    candidates = {}
    if candidate_ids:
        rows = (
            db.execute(
                select(NeoantigenCandidate).where(
                    NeoantigenCandidate.id.in_(candidate_ids)
                )
            )
            .scalars()
            .all()
        )
        candidates = {row.id: row for row in rows}
    predictions: dict = {}
    for result in db.execute(
        select(PredictionResult)
        .where(PredictionResult.candidate_id.in_(candidate_ids or [""]))
        .order_by(PredictionResult.created_at.desc())
    ).scalars().all():
        predictions.setdefault(result.candidate_id, result)
    rows_data = build_worklist(construct, candidates, predictions)
    return Response(
        content=worklist_csv(rows_data),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="worklist_{construct_id[:8]}.csv"'},
    )


@router.get("/constructs/{construct_id}/export")
def export(
    construct_id: str,
    format: str = Query(default="json", pattern="^(json|csv|report)$"),
    db: Session = Depends(get_db),
) -> Response:
    construct = _get_or_404(db, construct_id)
    try:
        content, media_type, filename = export_construct(db, construct, format)
    except ConstructError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
