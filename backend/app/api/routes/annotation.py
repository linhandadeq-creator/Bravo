from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.annotation.base import Consequence
from app.annotation.registry import list_providers
from app.core.config import settings
from app.db.session import get_db
from app.models.analysis_run import AnalysisRun
from app.models.annotation import AnnotationRun, VariantAnnotation
from app.models.project import Project
from app.models.variant import Variant
from app.schemas.annotation import (
    AnnotatedVariantRead,
    AnnotationRead,
    AnnotationRunRead,
    AnnotateRequest,
    FilterConfigRead,
    FilterConfigUpdate,
    ProviderRead,
    VariantDetailRead,
)
from app.schemas.variant import VariantRead
from app.schemas.evidence import EvidenceRecordRead
from app.services.annotation_engine import (
    AnnotationGateError,
    latest_annotation_run,
    require_traceable_annotations,
    run_annotation,
)
from app.services import evidence_service
from app.services.filtering import (
    apply_consequence_filter,
    get_allowed_consequences,
    set_allowed_consequences,
)

router = APIRouter(tags=["annotation"])


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


@router.get("/annotation/providers", response_model=list[ProviderRead])
def get_providers() -> list[dict]:
    return list_providers()


@router.get("/annotation/consequences", response_model=list[str])
def get_consequences() -> list[str]:
    return [consequence.value for consequence in Consequence]


@router.post(
    "/analysis-runs/{run_id}/annotate",
    response_model=AnnotationRunRead,
    status_code=status.HTTP_201_CREATED,
)
def annotate_run(
    run_id: str, payload: AnnotateRequest, db: Session = Depends(get_db)
) -> AnnotationRun:
    run = _get_run(db, run_id)
    provider = payload.provider or settings.ANNOTATION_DEFAULT_PROVIDER
    return run_annotation(db, run, provider, payload.parameters)


@router.get("/analysis-runs/{run_id}/annotation", response_model=AnnotationRunRead | None)
def get_latest_annotation(
    run_id: str, db: Session = Depends(get_db)
) -> AnnotationRun | None:
    _get_run(db, run_id)
    return latest_annotation_run(db, run_id)


@router.get("/analysis-runs/{run_id}/annotations", response_model=list[AnnotationRead])
def list_annotations(
    run_id: str, db: Session = Depends(get_db)
) -> list[VariantAnnotation]:
    run = _get_run(db, run_id)
    annotation_run = latest_annotation_run(db, run.id)
    if annotation_run is None:
        return []
    statement = (
        select(VariantAnnotation)
        .where(VariantAnnotation.annotation_run_id == annotation_run.id)
        .order_by(VariantAnnotation.consequence, VariantAnnotation.gene)
    )
    return list(db.execute(statement).scalars().all())


@router.get(
    "/analysis-runs/{run_id}/annotated-variants",
    response_model=list[AnnotatedVariantRead],
)
def list_annotated_variants(
    run_id: str,
    allowed: str | None = Query(
        default=None,
        description="Comma-separated override; defaults to the project filter config.",
    ),
    db: Session = Depends(get_db),
) -> list[AnnotatedVariantRead]:
    run = _get_run(db, run_id)
    annotation_run = latest_annotation_run(db, run.id)
    if annotation_run is None:
        return []

    if allowed is None:
        allowed_list = get_allowed_consequences(db, run.project_id)
    else:
        allowed_list = [item.strip() for item in allowed.split(",") if item.strip()]

    annotations = list(
        db.execute(
            select(VariantAnnotation).where(
                VariantAnnotation.annotation_run_id == annotation_run.id
            )
        )
        .scalars()
        .all()
    )
    filtered = apply_consequence_filter(annotations, allowed_list)

    variant_ids = [a.variant_id for a in filtered if a.variant_id]
    variants = {
        v.id: v
        for v in db.execute(select(Variant).where(Variant.id.in_(variant_ids)))
        .scalars()
        .all()
    }

    result: list[AnnotatedVariantRead] = []
    for annotation in filtered:
        variant = variants.get(annotation.variant_id or "")
        if variant is None:
            continue
        result.append(
            AnnotatedVariantRead(
                variant_id=variant.id,
                sample_role=variant.sample_role,
                chromosome=variant.chromosome_normalized or variant.chromosome,
                position=variant.position,
                reference=variant.reference,
                alternate=variant.alternate,
                variant_type=variant.variant_type,
                status=annotation.status,
                gene=annotation.gene,
                gene_id=annotation.gene_id,
                transcript=annotation.transcript,
                transcript_id=annotation.transcript_id,
                consequence=annotation.consequence,
                impact=annotation.impact,
                protein_change=annotation.protein_change,
                cds_position=annotation.cds_position,
                protein_position=annotation.protein_position,
            )
        )
    return result


@router.get(
    "/analysis-runs/{run_id}/neoantigen-input",
    response_model=list[AnnotatedVariantRead],
)
def neoantigen_input(
    run_id: str,
    db: Session = Depends(get_db),
) -> list[AnnotatedVariantRead]:
    """Gate: only variants with traceable annotations may proceed downstream."""
    run = _get_run(db, run_id)
    try:
        annotation_run, annotations = require_traceable_annotations(db, run)
    except AnnotationGateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    allowed = get_allowed_consequences(db, run.project_id)
    permitted = apply_consequence_filter(list(annotations.values()), allowed)
    variant_ids = [a.variant_id for a in permitted if a.variant_id]
    variants = {
        v.id: v
        for v in db.execute(select(Variant).where(Variant.id.in_(variant_ids)))
        .scalars()
        .all()
    }
    output: list[AnnotatedVariantRead] = []
    for annotation in permitted:
        variant = variants.get(annotation.variant_id or "")
        if variant is None or variant.sample_role == "NORMAL":
            continue
        output.append(
            AnnotatedVariantRead(
                variant_id=variant.id,
                sample_role=variant.sample_role,
                chromosome=variant.chromosome_normalized or variant.chromosome,
                position=variant.position,
                reference=variant.reference,
                alternate=variant.alternate,
                variant_type=variant.variant_type,
                status=annotation.status,
                gene=annotation.gene,
                gene_id=annotation.gene_id,
                transcript=annotation.transcript,
                transcript_id=annotation.transcript_id,
                consequence=annotation.consequence,
                impact=annotation.impact,
                protein_change=annotation.protein_change,
                cds_position=annotation.cds_position,
                protein_position=annotation.protein_position,
            )
        )
    return output


@router.get(
    "/analysis-runs/{run_id}/variants/{variant_id}",
    response_model=VariantDetailRead,
)
def variant_detail(
    run_id: str, variant_id: str, db: Session = Depends(get_db)
) -> VariantDetailRead:
    _get_run(db, run_id)
    variant = db.get(Variant, variant_id)
    if variant is None or variant.analysis_run_id != run_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    def evidence(role: str) -> Variant | None:
        statement = (
            select(Variant)
            .where(
                Variant.analysis_run_id == run_id,
                Variant.sample_role == role,
                Variant.chromosome_normalized == variant.chromosome_normalized,
                Variant.position == variant.position,
                Variant.reference == variant.reference,
                Variant.alternate == variant.alternate,
            )
            .limit(1)
        )
        return db.execute(statement).scalars().first()

    annotation_run = latest_annotation_run(db, run_id)
    annotation: VariantAnnotation | None = None
    if annotation_run is not None:
        annotation = (
            db.execute(
                select(VariantAnnotation)
                .where(
                    VariantAnnotation.annotation_run_id == annotation_run.id,
                    VariantAnnotation.variant_id == variant_id,
                )
                .limit(1)
            )
            .scalars()
            .first()
        )

    return VariantDetailRead(
        variant=VariantRead.model_validate(variant),
        tumor_evidence=VariantRead.model_validate(evidence("TUMOR")) if evidence("TUMOR") else None,
        normal_evidence=VariantRead.model_validate(evidence("NORMAL")) if evidence("NORMAL") else None,
        annotation=AnnotationRead.model_validate(annotation) if annotation else None,
        annotation_run=AnnotationRunRead.model_validate(annotation_run) if annotation_run else None,
        evidence=[
            EvidenceRecordRead.model_validate(record)
            for record in evidence_service.evidence_for_variant(db, variant_id)
        ],
    )


@router.get("/projects/{project_id}/annotation-filter", response_model=FilterConfigRead)
def get_filter(project_id: str, db: Session = Depends(get_db)) -> FilterConfigRead:
    _get_project(db, project_id)
    return FilterConfigRead(
        project_id=project_id,
        allowed_consequences=get_allowed_consequences(db, project_id),
    )


@router.put("/projects/{project_id}/annotation-filter", response_model=FilterConfigRead)
def update_filter(
    project_id: str, payload: FilterConfigUpdate, db: Session = Depends(get_db)
) -> FilterConfigRead:
    _get_project(db, project_id)
    valid = {consequence.value for consequence in Consequence}
    invalid = [c for c in payload.allowed_consequences if c not in valid]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown consequence(s): {', '.join(invalid)}",
        )
    config = set_allowed_consequences(db, project_id, payload.allowed_consequences)
    return FilterConfigRead(
        project_id=project_id, allowed_consequences=list(config.allowed_consequences or [])
    )
