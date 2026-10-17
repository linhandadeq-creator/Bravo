import base64

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.analysis_run import AnalysisRun
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportDetail, ReportRead
from app.services.report_service import (
    SUPPORTED_FORMATS,
    ReportError,
    build_report,
    collect_report_data,
    render_report,
    report_summary,
)

router = APIRouter(tags=["reports"])


def _get_run(db: Session, run_id: str) -> AnalysisRun:
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return run


@router.post(
    "/analysis-runs/{run_id}/reports",
    response_model=ReportDetail,
    status_code=status.HTTP_201_CREATED,
)
def generate_report(
    run_id: str, payload: ReportCreate, db: Session = Depends(get_db)
) -> Report:
    run = _get_run(db, run_id)
    if payload.format not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported report format '{payload.format}'",
        )
    data = collect_report_data(db, run)
    content, _media, _filename = render_report(data, payload.format)
    if isinstance(content, bytes):
        content = base64.b64encode(content).decode("ascii")
    report = Report(
        analysis_run_id=run.id,
        project_id=run.project_id,
        title=data["title"],
        format=payload.format,
        status="GENERATED",
        summary=report_summary(data),
        content=content,
        software_version=settings.APP_VERSION,
        generated_by=payload.generated_by,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/reports", response_model=list[ReportRead])
def list_reports(
    project_id: str | None = Query(default=None),
    analysis_run_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[Report]:
    statement = select(Report).order_by(Report.created_at.desc()).limit(limit)
    if project_id:
        statement = statement.where(Report.project_id == project_id)
    if analysis_run_id:
        statement = statement.where(Report.analysis_run_id == analysis_run_id)
    return list(db.execute(statement).scalars().all())


@router.get("/reports/{report_id}", response_model=ReportDetail)
def get_report(report_id: str, db: Session = Depends(get_db)) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.get("/reports/{report_id}/download")
def download_report(report_id: str, db: Session = Depends(get_db)) -> Response:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    media = {
        "json": "application/json",
        "markdown": "text/markdown",
        "html": "text/html",
        "csv": "text/csv",
        "pdf": "application/pdf",
    }.get(report.format, "text/plain")
    ext = {"json": "json", "markdown": "md", "html": "html", "csv": "csv", "pdf": "pdf"}.get(
        report.format, "txt"
    )
    if report.format == "pdf":
        content: str | bytes = base64.b64decode(report.content or "")
    else:
        content = report.content or ""
    return Response(
        content=content,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="report_{report.id[:8]}.{ext}"'
        },
    )


@router.get("/analysis-runs/{run_id}/report")
def download_run_report(
    run_id: str,
    format: str = Query(default="markdown", pattern="^(json|markdown|html|csv|pdf)$"),
    db: Session = Depends(get_db),
) -> Response:
    run = _get_run(db, run_id)
    try:
        content, media_type, filename = build_report(db, run, format)
    except ReportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
