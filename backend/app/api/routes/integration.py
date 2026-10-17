from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.expression.parsing import map_expression_record
from app.hla.normalization import map_hla_record, parse_hla_records
from app.models.analysis_run import MODE_SYNTHETIC, AnalysisRun
from app.models.expression import ExpressionQuantification, ExpressionRecord
from app.models.hla import HLAProfile
from app.models.project import Project
from app.models.sample import NORMAL, TUMOR, Sample
from app.schemas.expression import (
    ExpressionIngestRequest,
    ExpressionQuantificationRead,
    ExpressionRecordRead,
    ExpressionStatusRead,
)
from app.schemas.hla import HlaIngestRequest, HlaStatusRead, HLAProfileRead
from app.schemas.integration import IntegrationStatusRead, SyntheticIntegrationRead
from app.services.analysis import run_analysis
from app.services.uploads import read_text_limited
from app.services.annotation_engine import run_annotation
from app.services.expression_service import (
    expression_status,
    hash_content as expression_hash,
    ingest_records as ingest_expression_records,
    list_quantification as list_expression_quantification,
    list_records as list_expression_records,
    parse_and_ingest as parse_and_ingest_expression,
    quantify_matrix,
)
from app.services.hla_service import (
    hash_content as hla_hash,
    hla_status,
    ingest_records as ingest_hla_records,
    list_profiles,
    parse_and_ingest as parse_and_ingest_hla,
)
from app.services.readiness import ReadinessError, integration_status, require_neoantigen_readiness
from app.services.synthetic_integration import generate_synthetic_integration

router = APIRouter(tags=["integration"])

_FORMATS = ("json", "csv", "tsv")


def _get_run(db: Session, run_id: str) -> AnalysisRun:
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return run


def _get_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _infer_format(filename: str | None, fmt: str | None) -> str:
    if fmt and fmt.lower() in _FORMATS:
        return fmt.lower()
    suffix = Path(filename or "").suffix.lower().lstrip(".")
    if suffix in _FORMATS:
        return suffix
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unable to determine input format; provide fmt=json|csv|tsv",
    )


def _clear_hla(db: Session, run_id: str) -> None:
    db.execute(delete(HLAProfile).where(HLAProfile.analysis_run_id == run_id))
    db.commit()


def _clear_expression(db: Session, run_id: str) -> None:
    db.execute(delete(ExpressionRecord).where(ExpressionRecord.analysis_run_id == run_id))
    db.commit()


# ---------------------------------------------------------------- HLA --------
@router.get("/analysis-runs/{run_id}/hla", response_model=list[HLAProfileRead])
def get_hla(run_id: str, db: Session = Depends(get_db)) -> list[HLAProfile]:
    run = _get_run(db, run_id)
    return list_profiles(db, run.id)


@router.get("/analysis-runs/{run_id}/hla/status", response_model=HlaStatusRead)
def get_hla_status(run_id: str, db: Session = Depends(get_db)) -> dict:
    return hla_status(db, _get_run(db, run_id))


@router.post("/analysis-runs/{run_id}/hla/analyze")
def analyze_hla(run_id: str, db: Session = Depends(get_db)) -> dict:
    """Re-validate uploaded HLA profiles and return a detailed analysis."""
    run = _get_run(db, run_id)
    state = hla_status(db, run)
    profiles = []
    for profile in list_profiles(db, run.id):
        profiles.append(
            {
                "id": profile.id,
                "allele": profile.allele,
                "allele_raw": profile.allele_raw,
                "allele_class": profile.allele_class,
                "is_valid": profile.is_valid,
                "is_duplicate": profile.is_duplicate,
                "invalid_reason": profile.invalid_reason,
                "source": profile.source,
                "method": profile.method,
                "confidence": profile.confidence,
            }
        )
    state["profiles"] = profiles
    state["action"] = "hla_analyzed"
    return state


@router.post("/analysis-runs/{run_id}/hla", response_model=HlaStatusRead)
def add_hla_manual(
    run_id: str, payload: HlaIngestRequest, db: Session = Depends(get_db)
) -> dict:
    run = _get_run(db, run_id)
    _clear_hla(db, run.id)
    records = [map_hla_record(row) for row in payload.alleles]
    content = str(records)
    ingest_hla_records(
        db,
        run,
        records,
        source=payload.source,
        method=payload.method,
        version=payload.version,
        input_hash=hla_hash(content),
    )
    return hla_status(db, run)


@router.post("/analysis-runs/{run_id}/hla/upload", response_model=HlaStatusRead)
def upload_hla(
    run_id: str,
    file: UploadFile = File(...),
    fmt: str | None = Form(default=None),
    source: str | None = Form(default=None),
    method: str | None = Form(default=None),
    version: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict:
    run = _get_run(db, run_id)
    content = read_text_limited(file.file)
    try:
        # Parse first so a malformed file never clears valid existing HLA data.
        records = parse_hla_records(content, _infer_format(file.filename, fmt))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _clear_hla(db, run.id)
    ingest_hla_records(
        db, run, records, source=source, method=method, version=version,
        input_hash=hla_hash(content),
    )
    return hla_status(db, run)


# --------------------------------------------------------- Expression --------
@router.get(
    "/analysis-runs/{run_id}/expression", response_model=list[ExpressionRecordRead]
)
def get_expression(run_id: str, db: Session = Depends(get_db)) -> list[ExpressionRecord]:
    run = _get_run(db, run_id)
    return list_expression_records(db, run.id)


@router.get(
    "/analysis-runs/{run_id}/expression/status", response_model=ExpressionStatusRead
)
def get_expression_status(run_id: str, db: Session = Depends(get_db)) -> dict:
    return expression_status(db, _get_run(db, run_id))


@router.post("/analysis-runs/{run_id}/expression/analyze")
def analyze_expression(run_id: str, db: Session = Depends(get_db)) -> dict:
    """Re-validate uploaded expression data and return a detailed analysis."""
    run = _get_run(db, run_id)
    state = expression_status(db, run)
    records = list_expression_records(db, run.id)
    state["top_expressed"] = [
        {
            "gene_id": record.gene_id,
            "gene_symbol": record.gene_symbol,
            "expression_value": record.expression_value,
            "unit": record.unit,
            "level": record.level,
            "is_valid": record.is_valid,
        }
        for record in sorted(
            (r for r in records if r.is_valid and r.expression_value is not None),
            key=lambda r: r.expression_value,
            reverse=True,
        )[:20]
    ]
    state["action"] = "expression_analyzed"
    return state


@router.post("/analysis-runs/{run_id}/expression", response_model=ExpressionStatusRead)
def add_expression_manual(
    run_id: str, payload: ExpressionIngestRequest, db: Session = Depends(get_db)
) -> dict:
    run = _get_run(db, run_id)
    _clear_expression(db, run.id)
    records = [map_expression_record(row) for row in payload.records]
    ingest_expression_records(
        db,
        run,
        records,
        source=payload.source,
        version=payload.version,
        default_unit=payload.unit,
        input_hash=expression_hash(str(records)),
    )
    return expression_status(db, run)


@router.post(
    "/analysis-runs/{run_id}/expression/upload", response_model=ExpressionStatusRead
)
def upload_expression(
    run_id: str,
    file: UploadFile = File(...),
    fmt: str | None = Form(default=None),
    source: str | None = Form(default=None),
    version: str | None = Form(default=None),
    unit: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict:
    run = _get_run(db, run_id)
    _clear_expression(db, run.id)
    content = read_text_limited(file.file)
    try:
        parse_and_ingest_expression(
            db,
            run,
            content,
            _infer_format(file.filename, fmt),
            source,
            version,
            default_unit=unit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return expression_status(db, run)


@router.post("/analysis-runs/{run_id}/expression/quantify")
def quantify_expression(
    run_id: str,
    file: UploadFile = File(...),
    fmt: str | None = Form(default=None),
    tumor_samples: str | None = Form(default=None),
    normal_samples: str | None = Form(default=None),
    unit: str | None = Form(default=None),
    source: str | None = Form(default=None),
    version: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Quantify a genes × samples expression matrix (tumor vs normal).

    The matrix must either contain paired columns (``tumor_tpm`` /
    ``normal_tpm``, or ``tumor`` / ``normal``) or declare the sample columns
    with ``tumor_samples`` / ``normal_samples`` (comma-separated column names).
    Produces per-gene tumor/normal means, log2 fold change and expression
    calls (method rnaseq-matrix-v1). Not read-alignment based.
    """
    run = _get_run(db, run_id)
    content = read_text_limited(file.file)
    tumor_cols = [item.strip() for item in (tumor_samples or "").split(",") if item.strip()]
    normal_cols = [item.strip() for item in (normal_samples or "").split(",") if item.strip()]
    try:
        return quantify_matrix(
            db,
            run,
            content,
            _infer_format(file.filename, fmt),
            tumor_samples=tumor_cols or None,
            normal_samples=normal_cols or None,
            unit=unit,
            source=source,
            version=version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/analysis-runs/{run_id}/expression/quantification",
    response_model=list[ExpressionQuantificationRead],
)
def get_quantification(
    run_id: str,
    differentially_expressed: bool | None = None,
    gene_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[ExpressionQuantification]:
    _get_run(db, run_id)
    return list_expression_quantification(
        db, run_id, differentially_expressed=differentially_expressed, gene_id=gene_id
    )


# -------------------------------------------------------- Integration --------
@router.get("/analysis-runs/{run_id}/population-coverage")
def get_population_coverage(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = _get_run(db, run_id)
    alleles = [
        profile.allele
        for profile in list_profiles(db, run.id)
        if profile.is_valid and not profile.is_duplicate and profile.allele
    ]
    from app.services.population_coverage import estimate

    result = estimate(alleles)
    result["run_id"] = run.id
    result["alleles"] = sorted(set(alleles))
    return result


@router.get(
    "/analysis-runs/{run_id}/integration-status",
    response_model=IntegrationStatusRead,
)
def get_integration_status(run_id: str, db: Session = Depends(get_db)) -> dict:
    return integration_status(db, _get_run(db, run_id))


@router.get(
    "/analysis-runs/{run_id}/neoantigen-readiness",
    response_model=IntegrationStatusRead,
)
def get_neoantigen_readiness(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = _get_run(db, run_id)
    try:
        return require_neoantigen_readiness(db, run)
    except ReadinessError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/projects/{project_id}/synthetic-integration",
    response_model=SyntheticIntegrationRead,
    status_code=status.HTTP_201_CREATED,
)
def synthetic_integration(
    project_id: str, db: Session = Depends(get_db)
) -> SyntheticIntegrationRead:
    _get_project(db, project_id)

    directory = settings.storage_path / "synthetic_integration"
    dataset = generate_synthetic_integration(directory)

    tumor = Sample(
        project_id=project_id,
        name="Synthetic Integration Tumor",
        sample_type=TUMOR,
        reference_build=dataset.reference_build,
        original_filename=Path(dataset.tumor_path).name,
        storage_path=dataset.tumor_path,
        file_size_bytes=Path(dataset.tumor_path).stat().st_size,
        source="SYNTHETIC",
    )
    normal = Sample(
        project_id=project_id,
        name="Synthetic Integration Normal",
        sample_type=NORMAL,
        reference_build=dataset.reference_build,
        original_filename=Path(dataset.normal_path).name,
        storage_path=dataset.normal_path,
        file_size_bytes=Path(dataset.normal_path).stat().st_size,
        source="SYNTHETIC",
    )

    run = run_analysis(
        db,
        project_id=project_id,
        tumor_sample=tumor,
        normal_sample=normal,
        reference_build=dataset.reference_build,
        mode=MODE_SYNTHETIC,
    )
    run_annotation(db, run, "mock")

    hla_content = Path(dataset.hla_path).read_text()
    parse_and_ingest_hla(
        db, run, hla_content, "json", source="synthetic", method="mock-typing", version="1.0.0"
    )
    expression_content = Path(dataset.expression_path).read_text()
    parse_and_ingest_expression(
        db, run, expression_content, "tsv", source="synthetic", version="1.0.0"
    )

    report = integration_status(db, run)
    return SyntheticIntegrationRead(
        analysis_run_id=run.id,
        status=report["status"],
        hla_status=report["hla"]["status"],
        expression_status=report["expression"]["status"],
        linked_genes=report["linked_genes"],
    )
