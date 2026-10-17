from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.reference import DEFAULT_REFERENCE_BUILD, normalize_reference_build
from app.db.session import get_db
from app.models.analysis_run import MODE_SYNTHETIC, MODE_UPLOAD, AnalysisRun
from app.models.project import Project
from app.models.sample import NORMAL, TUMOR, Sample
from app.models.somatic_candidate import SomaticCandidate
from app.models.variant import Variant
from app.schemas.analysis_run import AnalysisRunCreate, AnalysisRunRead, SyntheticRunRequest
from app.schemas.somatic_candidate import SomaticCandidateRead
from app.schemas.variant import VariantRead
from app.services.analysis import new_synthetic_directory, run_analysis, save_upload
from app.services.synthetic import generate_synthetic_dataset

router = APIRouter(prefix="/analysis-runs", tags=["analysis-runs"])


def _get_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _get_run(db: Session, run_id: str) -> AnalysisRun:
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return run


def _get_sample(db: Session, sample_id: str, sample_type: str) -> Sample:
    sample = db.get(Sample, sample_id)
    if sample is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{sample_type} sample not found: {sample_id}",
        )
    return sample


@router.post("/synthetic", response_model=AnalysisRunRead, status_code=status.HTTP_201_CREATED)
def create_synthetic_run(
    payload: SyntheticRunRequest, db: Session = Depends(get_db)
) -> AnalysisRun:
    _get_project(db, payload.project_id)

    dataset = generate_synthetic_dataset(new_synthetic_directory())
    build = normalize_reference_build(payload.reference_build) or dataset.reference_build

    tumor = Sample(
        project_id=payload.project_id,
        name="Synthetic Tumor",
        sample_type=TUMOR,
        reference_build=build,
        original_filename=Path(dataset.tumor_path).name,
        storage_path=dataset.tumor_path,
        file_size_bytes=Path(dataset.tumor_path).stat().st_size,
        source="SYNTHETIC",
    )
    normal = Sample(
        project_id=payload.project_id,
        name="Synthetic Normal",
        sample_type=NORMAL,
        reference_build=build,
        original_filename=Path(dataset.normal_path).name,
        storage_path=dataset.normal_path,
        file_size_bytes=Path(dataset.normal_path).stat().st_size,
        source="SYNTHETIC",
    )

    return run_analysis(
        db,
        project_id=payload.project_id,
        tumor_sample=tumor,
        normal_sample=normal,
        reference_build=build,
        mode=MODE_SYNTHETIC,
    )


@router.post("/upload", response_model=AnalysisRunRead, status_code=status.HTTP_201_CREATED)
def upload_run(
    project_id: str = Form(...),
    tumor_file: UploadFile = File(...),
    normal_file: UploadFile | None = File(default=None),
    reference_build: str | None = Form(default=None),
    tumor_reference_build: str | None = Form(default=None),
    normal_reference_build: str | None = Form(default=None),
    tumor_name: str | None = Form(default=None),
    normal_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> AnalysisRun:
    _get_project(db, project_id)

    tumor_build = normalize_reference_build(tumor_reference_build or reference_build)
    normal_build = normalize_reference_build(normal_reference_build or reference_build)
    run_build = normalize_reference_build(reference_build) or tumor_build

    tumor = Sample(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=tumor_name or "Tumor Sample",
        sample_type=TUMOR,
        reference_build=tumor_build,
        original_filename=tumor_file.filename,
        source="UPLOAD",
    )
    tumor.storage_path, tumor.file_size_bytes = save_upload(
        tumor_file.file, project_id, tumor_file.filename, f"tumor_{tumor.id}"
    )

    normal: Sample | None = None
    if normal_file is not None and normal_file.filename:
        normal = Sample(
            id=str(uuid.uuid4()),
            project_id=project_id,
            name=normal_name or "Normal Sample",
            sample_type=NORMAL,
            reference_build=normal_build,
            original_filename=normal_file.filename,
            source="UPLOAD",
        )
        normal.storage_path, normal.file_size_bytes = save_upload(
            normal_file.file, project_id, normal_file.filename, f"normal_{normal.id}"
        )

    return run_analysis(
        db,
        project_id=project_id,
        tumor_sample=tumor,
        normal_sample=normal,
        reference_build=run_build,
        mode=MODE_UPLOAD,
    )


@router.post("", response_model=AnalysisRunRead, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: AnalysisRunCreate, db: Session = Depends(get_db)
) -> AnalysisRun:
    _get_project(db, payload.project_id)
    tumor = _get_sample(db, payload.tumor_sample_id, TUMOR)
    normal = _get_sample(db, payload.normal_sample_id, NORMAL)

    return run_analysis(
        db,
        project_id=payload.project_id,
        tumor_sample=tumor,
        normal_sample=normal,
        reference_build=payload.reference_build
        or tumor.reference_build
        or DEFAULT_REFERENCE_BUILD,
        mode=MODE_UPLOAD,
    )


@router.get("", response_model=list[AnalysisRunRead])
def list_runs(
    project_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[AnalysisRun]:
    statement = select(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(limit)
    if project_id:
        statement = statement.where(AnalysisRun.project_id == project_id)
    return list(db.execute(statement).scalars().all())


@router.get("/{run_id}", response_model=AnalysisRunRead)
def get_run(run_id: str, db: Session = Depends(get_db)) -> AnalysisRun:
    return _get_run(db, run_id)


@router.get("/{run_id}/variants", response_model=list[VariantRead])
def list_run_variants(
    run_id: str,
    role: str | None = Query(default=None, pattern="^(TUMOR|NORMAL)$"),
    valid_only: bool = Query(default=False),
    include_duplicates: bool = Query(default=True),
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[Variant]:
    _get_run(db, run_id)
    statement = (
        select(Variant)
        .where(Variant.analysis_run_id == run_id)
        .order_by(Variant.sample_role, Variant.chromosome_normalized, Variant.position)
        .limit(limit)
    )
    if role:
        statement = statement.where(Variant.sample_role == role)
    if valid_only:
        statement = statement.where(Variant.is_valid.is_(True))
    if not include_duplicates:
        statement = statement.where(Variant.is_duplicate.is_(False))
    return list(db.execute(statement).scalars().all())


@router.get("/{run_id}/somatic-candidates", response_model=list[SomaticCandidateRead])
def list_somatic_candidates(
    run_id: str,
    classification: str | None = Query(
        default=None, pattern="^(TUMOR_ONLY|NORMAL_ONLY|SHARED|UNCERTAIN)$"
    ),
    db: Session = Depends(get_db),
) -> list[SomaticCandidate]:
    _get_run(db, run_id)
    statement = (
        select(SomaticCandidate)
        .where(SomaticCandidate.analysis_run_id == run_id)
        .order_by(SomaticCandidate.chromosome, SomaticCandidate.position)
    )
    if classification:
        statement = statement.where(SomaticCandidate.classification == classification)
    return list(db.execute(statement).scalars().all())
