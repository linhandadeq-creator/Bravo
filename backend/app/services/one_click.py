"""One-click orchestration (shared by the synchronous route and async jobs).

Runs the full validated pipeline: upload → QC → annotation → HLA → expression →
candidates → prediction → ranking → construct → blueprint → report. Reports its
progress through a callback and honours a cancellation callback between stages,
so the same code drives both the sync endpoint and the background job worker.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Callable
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.reference import DEFAULT_REFERENCE_BUILD, normalize_reference_build
from app.models.analysis_run import MODE_SYNTHETIC, MODE_UPLOAD, AnalysisRun
from app.models.neoantigen import NeoantigenCandidate
from app.models.project import Project
from app.models.report import Report
from app.models.sample import NORMAL, TUMOR, Sample
from app.schemas.generate import OneClickResult, PipelineStage
from app.services.annotation_engine import run_annotation
from app.services.analysis import run_analysis, save_upload
from app.services.blueprint_service import DISCLAIMER, build_blueprint
from app.services.construct_service import create_construct
from app.services.expression_service import (
    EXPRESSION_AVAILABLE,
    expression_status,
    parse_and_ingest as parse_and_ingest_expression,
)
from app.services.hla_service import (
    HLA_AVAILABLE,
    hla_status,
    parse_and_ingest as parse_and_ingest_hla,
)
from app.services.neoantigen_service import run_neoantigen_engine
from app.services.report_service import collect_report_data, render_report
from app.services.synthetic_integration import SYNTHETIC_HLA

_FORMATS = ("json", "csv", "tsv")


class CancelledError(RuntimeError):
    """Raised when the caller cancels a running job."""


@dataclass
class OneClickParams:
    project_name: str = "One-Click Project"
    project_id: str | None = None
    reference_build: str = DEFAULT_REFERENCE_BUILD
    provider: str = "mock"
    annotation_provider: str = "mock"
    top_n: int = 5
    simulation_format: str = "mRNA-LNP"
    use_synthetic_context: bool = False
    demo: bool = False


@dataclass
class OneClickUploads:
    tumor: BinaryIO | None = None
    tumor_name: str | None = None
    normal: BinaryIO | None = None
    normal_name: str | None = None
    hla_text: str | None = None
    hla_format: str = "json"
    expression_text: str | None = None
    expression_format: str = "tsv"


ProgressCb = Callable[[str, str, str | None], None]
CancelCb = Callable[[], bool]


def infer_format(filename: str | None, fmt: str | None) -> str:
    if fmt and fmt.lower() in _FORMATS:
        return fmt.lower()
    suffix = Path(filename or "").suffix.lower().lstrip(".")
    if suffix in _FORMATS:
        return suffix
    return "json"


class _Reporter:
    def __init__(self, progress: ProgressCb | None) -> None:
        self.stages: list[PipelineStage] = []
        self.progress = progress

    def emit(self, step: str, status: str, detail: str | None = None) -> None:
        self.stages.append(PipelineStage(step=step, status=status, detail=detail))
        if self.progress:
            self.progress(step, status, detail)


def _get_or_create_project(db: Session, name: str) -> Project:
    project = db.execute(select(Project).where(Project.name == name)).scalars().first()
    if project is None:
        project = Project(
            name=name, description="One-click auto-generated project", status="active"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
    return project


def _resolve_project(db: Session, params: "OneClickParams") -> Project:
    """Use the selected project when given, otherwise create/lookup by name."""
    if params.project_id:
        project = db.get(Project, params.project_id)
        if project is None:
            raise ValueError(f"Project not found: {params.project_id}")
        return project
    return _get_or_create_project(db, params.project_name)


def _qc_detail(run: AnalysisRun) -> str:
    """Compact QC output preview shown in the pipeline's output window."""
    qc = run.qc_summary or {}
    somatic = qc.get("somatic") or run.somatic_summary or {}
    parts = [
        f"raw {qc.get('raw_variants', '—')}",
        f"valid {qc.get('valid_variants', '—')}",
        f"invalid {qc.get('invalid_variants', '—')}",
        f"duplicate {qc.get('duplicate_variants', '—')}",
        f"tumour-only {somatic.get('TUMOR_ONLY', '—')}",
        f"shared {somatic.get('SHARED', '—')}",
    ]
    return " · ".join(str(part) for part in parts)


def _select_top_candidates(
    db: Session, run_id: str, top_n: int
) -> list[NeoantigenCandidate]:
    rows = list(
        db.execute(
            select(NeoantigenCandidate)
            .where(
                NeoantigenCandidate.analysis_run_id == run_id,
                NeoantigenCandidate.status == "RANKED",
            )
            .order_by(NeoantigenCandidate.ranking_score.desc().nullslast())
        )
        .scalars()
        .all()
    )
    chosen: list[NeoantigenCandidate] = []
    seen_genes: set[str] = set()
    for row in rows:
        if row.gene and row.gene in seen_genes and len(chosen) < top_n:
            continue
        chosen.append(row)
        if row.gene:
            seen_genes.add(row.gene)
        if len(chosen) >= top_n:
            break
    return chosen


def _blocked(project: Project, run: AnalysisRun, reporter: _Reporter, message: str) -> OneClickResult:
    reporter.emit("PIPELINE", "BLOCKED", message)
    return OneClickResult(
        status="BLOCKED",
        message=message,
        project_id=project.id,
        analysis_run_id=run.id,
        stages=reporter.stages,
        disclaimer=DISCLAIMER,
    )


def _finish(
    db: Session,
    project: Project,
    run: AnalysisRun,
    params: OneClickParams,
    reporter: _Reporter,
    cancel: CancelCb | None,
) -> OneClickResult:
    if cancel and cancel():
        raise CancelledError()
    engine = run_neoantigen_engine(db, run, params.provider)
    reporter.emit(
        "NEOANTIGEN",
        engine["prediction"]["provider_status"],
        detail=(
            f"generated {engine['generated']} · rejected {engine['rejected']} · "
            f"ranked {engine['ranking']['ranked']}"
        ),
    )
    if cancel and cancel():
        raise CancelledError()

    candidates = _select_top_candidates(db, run.id, max(1, params.top_n))
    if not candidates:
        return _blocked(
            project, run, reporter, "No ranked candidates available; cannot build a construct."
        )

    construct = create_construct(
        db,
        run,
        [c.id for c in candidates],
        "One-Click mRNA Construct",
        params.simulation_format,
        "one-click",
    )
    reporter.emit(
        "CONSTRUCT",
        construct.status,
        detail=(
            f"{construct.simulation_format} · "
            f"{len(construct.sequence or '')} nt · {construct.status}"
        ),
    )
    if cancel and cancel():
        raise CancelledError()

    blueprint = build_blueprint(db, construct)

    data = collect_report_data(db, run)
    content, _media, _filename = render_report(data, "html")
    report = Report(
        analysis_run_id=run.id,
        project_id=run.project_id,
        title=data["title"],
        format="html",
        status="GENERATED",
        summary={
            "candidate_count": len(blueprint["segments"]),
            "blueprint_construct_id": construct.id,
        },
        content=content,
        software_version=settings.APP_VERSION,
        generated_by="one-click",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    reporter.emit("REPORT", "GENERATED", detail=f"{report.format} · {report.id[:8]}")

    return OneClickResult(
        status="SUCCESS",
        message="Generated the mRNA vaccine blueprint (research simulation).",
        project_id=project.id,
        analysis_run_id=run.id,
        construct_id=construct.id,
        report_id=report.id,
        candidate_count=len(candidates),
        stages=reporter.stages,
        blueprint=blueprint,
        report_formats=["html", "markdown", "json", "csv"],
        disclaimer=DISCLAIMER,
    )


def execute_one_click(
    db: Session,
    params: OneClickParams,
    uploads: OneClickUploads | None = None,
    *,
    progress: ProgressCb | None = None,
    cancel: CancelCb | None = None,
) -> OneClickResult:
    uploads = uploads or OneClickUploads()
    reporter = _Reporter(progress)
    build = normalize_reference_build(params.reference_build) or DEFAULT_REFERENCE_BUILD
    project = _resolve_project(db, params)

    if cancel and cancel():
        raise CancelledError()

    if params.demo:
        from app.services.synthetic_integration import generate_synthetic_integration

        dataset = generate_synthetic_integration(settings.storage_path / "one_click_demo")
        tumor = Sample(
            project_id=project.id,
            name="One-click demo tumour",
            sample_type=TUMOR,
            reference_build=dataset.reference_build,
            original_filename=Path(dataset.tumor_path).name,
            storage_path=dataset.tumor_path,
            file_size_bytes=Path(dataset.tumor_path).stat().st_size,
            source="SYNTHETIC",
        )
        normal = Sample(
            project_id=project.id,
            name="One-click demo normal",
            sample_type=NORMAL,
            reference_build=dataset.reference_build,
            original_filename=Path(dataset.normal_path).name,
            storage_path=dataset.normal_path,
            file_size_bytes=Path(dataset.normal_path).stat().st_size,
            source="SYNTHETIC",
        )
        run = run_analysis(
            db,
            project_id=project.id,
            tumor_sample=tumor,
            normal_sample=normal,
            reference_build=dataset.reference_build,
            mode=MODE_SYNTHETIC,
        )
        reporter.emit("VCF_QC", run.status, _qc_detail(run))
        annotation_run = run_annotation(db, run, params.annotation_provider)
        reporter.emit(
            "ANNOTATION",
            "ANNOTATED",
            detail=(
                f"{params.annotation_provider} · "
                f"{getattr(annotation_run, 'variant_count', None) or 0} variants"
            ),
        )
        parse_and_ingest_hla(
            db, run, Path(dataset.hla_path).read_text(), "json", "one-click", "mock-typing", "1.0.0"
        )
        parse_and_ingest_expression(
            db, run, Path(dataset.expression_path).read_text(), "tsv", "one-click", "1.0.0"
        )
        hla_state = hla_status(db, run)
        expr_state = expression_status(db, run)
        reporter.emit(
            "HLA_EXPRESSION",
            "INGESTED",
            detail=(
                f"HLA I {hla_state.get('class_i', 0)} · II {hla_state.get('class_ii', 0)} · "
                f"expression {expr_state.get('valid', 0)} records"
            ),
        )
        return _finish(db, project, run, params, reporter, cancel)

    # ---- uploaded files path ------------------------------------------------
    if uploads.tumor is None or not uploads.tumor_name:
        raise ValueError("Missing tumour VCF file (tumor_file)")

    tumor = Sample(
        id=str(uuid.uuid4()),
        project_id=project.id,
        name="User tumour sample",
        sample_type=TUMOR,
        reference_build=build,
        original_filename=uploads.tumor_name,
        source="UPLOAD",
    )
    tumor.storage_path, tumor.file_size_bytes = save_upload(
        uploads.tumor, project.id, uploads.tumor_name, f"tumor_{tumor.id}"
    )

    normal: Sample | None = None
    if uploads.normal is not None and uploads.normal_name:
        normal = Sample(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="User normal sample",
            sample_type=NORMAL,
            reference_build=build,
            original_filename=uploads.normal_name,
            source="UPLOAD",
        )
        normal.storage_path, normal.file_size_bytes = save_upload(
            uploads.normal, project.id, uploads.normal_name, f"normal_{normal.id}"
        )

    if cancel and cancel():
        raise CancelledError()
    run = run_analysis(
        db,
        project_id=project.id,
        tumor_sample=tumor,
        normal_sample=normal,
        reference_build=build,
        mode=MODE_UPLOAD,
    )
    reporter.emit("VCF_QC", run.status, _qc_detail(run) if run.status == "PASS" else run.error_message)
    if run.status != "PASS":
        message = run.error_message or "QC failed"
        if "Normal VCF is required" in message:
            message = "Normal VCF missing; tumour/normal pairing is required."
        elif "Reference build mismatch" in message:
            message = "Tumour and normal reference builds differ; rejected."
        return _blocked(project, run, reporter, message)

    if cancel and cancel():
        raise CancelledError()
    annotation_run = run_annotation(db, run, params.annotation_provider)
    reporter.emit(
        "ANNOTATION",
        "ANNOTATED",
        detail=(
            f"{params.annotation_provider} · "
            f"{getattr(annotation_run, 'variant_count', None) or 0} variants"
        ),
    )

    if uploads.hla_text:
        parse_and_ingest_hla(db, run, uploads.hla_text, uploads.hla_format, "user-upload", "user", "1.0.0")
        hla_state = hla_status(db, run)
        reporter.emit(
            "HLA",
            "INGESTED",
            detail=f"I {hla_state.get('class_i', 0)} · II {hla_state.get('class_ii', 0)} · valid {hla_state.get('valid', 0)}",
        )
    elif params.use_synthetic_context:
        import json as _json

        parse_and_ingest_hla(
            db, run, _json.dumps({"alleles": SYNTHETIC_HLA}), "json", "synthetic-context", "mock-typing", "1.0.0"
        )
        reporter.emit("HLA", "SYNTHETIC_CONTEXT")
    else:
        reporter.emit("HLA", "MISSING")

    if uploads.expression_text:
        parse_and_ingest_expression(db, run, uploads.expression_text, uploads.expression_format, "user-upload", "1.0.0")
        expr_state = expression_status(db, run)
        reporter.emit(
            "EXPRESSION",
            "INGESTED",
            detail=f"{expr_state.get('valid', 0)} records",
        )
    elif params.use_synthetic_context:
        from app.services.synthetic_integration import (
            generate_synthetic_integration as _gen,
        )

        dataset = _gen(settings.storage_path / "one_click_demo")
        parse_and_ingest_expression(
            db, run, Path(dataset.expression_path).read_text(), "tsv", "synthetic-context", "1.0.0"
        )
        reporter.emit("EXPRESSION", "SYNTHETIC_CONTEXT")
    else:
        reporter.emit("EXPRESSION", "MISSING")

    hla = hla_status(db, run)
    expression = expression_status(db, run)
    if hla["status"] != HLA_AVAILABLE:
        return _blocked(project, run, reporter, f"HLA: {hla['message']}")
    if expression["status"] != EXPRESSION_AVAILABLE:
        return _blocked(project, run, reporter, f"Expression: {expression['message']}")

    return _finish(db, project, run, params, reporter, cancel)
