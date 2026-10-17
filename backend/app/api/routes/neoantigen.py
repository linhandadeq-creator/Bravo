from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.analysis_run import AnalysisRun
from app.models.annotation import VariantAnnotation
from app.models.neoantigen import NeoantigenCandidate, PredictionResult
from app.models.project import Project
from app.models.variant import Variant
from app.prediction import list_prediction_providers
from app.ranking.engine import DEFAULT_WEIGHTS, DISCLAIMER
from app.schemas.annotation import AnnotationRead
from app.schemas.neoantigen import (
    CandidateDetailRead,
    NeoantigenCandidateRead,
    NeoantigenRunRequest,
    NeoantigenRunSummary,
    PredictionProviderRead,
    PredictionResultRead,
    RankingConfigRead,
    RankingConfigUpdate,
)
from app.schemas.variant import VariantRead
from app.services.neoantigen_service import (
    NeoantigenError,
    generate_candidates,
    get_or_create_ranking_config,
    predict_candidates,
    rank_candidates,
    run_neoantigen_engine,
)

router = APIRouter(tags=["neoantigen"])


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


@router.get("/prediction/providers", response_model=list[PredictionProviderRead])
def get_prediction_providers() -> list[dict]:
    return list_prediction_providers()


def _rank_to_read(config) -> RankingConfigRead:
    return RankingConfigRead(
        id=config.id,
        project_id=config.project_id,
        name=config.name,
        weights=config.weights or DEFAULT_WEIGHTS,
        version=config.version,
        disclaimer=DISCLAIMER,
    )


@router.get("/projects/{project_id}/ranking-config", response_model=RankingConfigRead)
def get_ranking_config(project_id: str, db: Session = Depends(get_db)) -> RankingConfigRead:
    _get_project(db, project_id)
    return _rank_to_read(get_or_create_ranking_config(db, project_id))


@router.put("/projects/{project_id}/ranking-config", response_model=RankingConfigRead)
def update_ranking_config(
    project_id: str, payload: RankingConfigUpdate, db: Session = Depends(get_db)
) -> RankingConfigRead:
    _get_project(db, project_id)
    invalid = [key for key in payload.weights if key not in DEFAULT_WEIGHTS]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown weight key(s): {', '.join(invalid)}",
        )
    if any(value < 0 for value in payload.weights.values()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Weights must be non-negative",
        )
    config = get_or_create_ranking_config(db, project_id)
    config.weights = {**DEFAULT_WEIGHTS, **payload.weights}
    db.commit()
    db.refresh(config)
    return _rank_to_read(config)


@router.post(
    "/analysis-runs/{run_id}/neoantigen/generate",
    response_model=list[NeoantigenCandidateRead],
    status_code=status.HTTP_201_CREATED,
)
def generate(
    run_id: str, db: Session = Depends(get_db)
) -> list[NeoantigenCandidate]:
    run = _get_run(db, run_id)
    try:
        return generate_candidates(db, run)
    except NeoantigenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/analysis-runs/{run_id}/neoantigen/predict")
def predict(
    run_id: str, payload: NeoantigenRunRequest, db: Session = Depends(get_db)
) -> dict:
    run = _get_run(db, run_id)
    provider = payload.provider or "mock"
    try:
        return predict_candidates(db, run, provider)
    except NeoantigenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/analysis-runs/{run_id}/neoantigen/rank")
def rank(
    run_id: str, payload: NeoantigenRunRequest, db: Session = Depends(get_db)
) -> dict:
    run = _get_run(db, run_id)
    return rank_candidates(db, run, weights=payload.weights)


@router.post(
    "/analysis-runs/{run_id}/neoantigen/run", response_model=NeoantigenRunSummary
)
def run_engine(
    run_id: str, payload: NeoantigenRunRequest, db: Session = Depends(get_db)
) -> dict:
    run = _get_run(db, run_id)
    provider = payload.provider or "mock"
    try:
        return run_neoantigen_engine(db, run, provider, weights=payload.weights)
    except NeoantigenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/analysis-runs/{run_id}/neoantigen-candidates",
    response_model=list[NeoantigenCandidateRead],
)
def list_candidates(
    run_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    prediction_status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    min_score: float | None = Query(default=None),
    sort: str = Query(default="score_desc"),
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[NeoantigenCandidate]:
    _get_run(db, run_id)
    statement = select(NeoantigenCandidate).where(
        NeoantigenCandidate.analysis_run_id == run_id
    )
    if status_filter:
        statement = statement.where(NeoantigenCandidate.status == status_filter)
    if prediction_status:
        statement = statement.where(
            NeoantigenCandidate.prediction_status == prediction_status
        )
    if min_score is not None:
        statement = statement.where(NeoantigenCandidate.ranking_score >= min_score)
    if search:
        pattern = f"%{search.lower()}%"
        statement = statement.where(
            NeoantigenCandidate.gene.ilike(pattern)
            | NeoantigenCandidate.protein_change.ilike(pattern)
            | NeoantigenCandidate.hla_allele.ilike(pattern)
            | NeoantigenCandidate.peptide_representation.ilike(pattern)
        )

    if sort == "score_asc":
        statement = statement.order_by(NeoantigenCandidate.ranking_score.asc().nullslast())
    elif sort == "gene":
        statement = statement.order_by(NeoantigenCandidate.gene.asc())
    else:
        statement = statement.order_by(NeoantigenCandidate.ranking_score.desc().nullslast())

    return list(db.execute(statement.limit(limit)).scalars().all())


@router.get(
    "/neoantigen-candidates/{candidate_id}", response_model=CandidateDetailRead
)
def candidate_detail(
    candidate_id: str, db: Session = Depends(get_db)
) -> CandidateDetailRead:
    candidate = db.get(NeoantigenCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    variant = db.get(Variant, candidate.variant_id) if candidate.variant_id else None
    annotation = None
    if candidate.variant_id:
        annotation = (
            db.execute(
                select(VariantAnnotation)
                .where(VariantAnnotation.variant_id == candidate.variant_id)
                .order_by(VariantAnnotation.created_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

    predictions = list(
        db.execute(
            select(PredictionResult)
            .where(PredictionResult.candidate_id == candidate.id)
            .order_by(PredictionResult.created_at.desc())
        )
        .scalars()
        .all()
    )
    provider = predictions[0].provider if predictions else None
    provider_version = predictions[0].provider_version if predictions else None
    provider_is_mock = candidate.prediction_status == "MOCK"

    return CandidateDetailRead(
        candidate=NeoantigenCandidateRead.model_validate(candidate),
        variant=VariantRead.model_validate(variant) if variant else None,
        annotation=AnnotationRead.model_validate(annotation) if annotation else None,
        predictions=[PredictionResultRead.model_validate(p) for p in predictions],
        provider=provider,
        provider_version=provider_version,
        provider_is_mock=provider_is_mock,
        disclaimer=DISCLAIMER,
    )
