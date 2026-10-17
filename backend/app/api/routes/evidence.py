"""Variant evidence endpoints: provider status and per-run annotation."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.evidence.registry import list_evidence_providers
from app.models.analysis_run import AnalysisRun
from app.schemas.evidence import (
    EvidenceAnnotateRequest,
    EvidenceProviderRead,
    EvidenceRecordRead,
)
from app.services import evidence_service

router = APIRouter(tags=["evidence"])


def _get_run(db: Session, run_id: str) -> AnalysisRun:
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found"
        )
    return run


@router.get("/evidence/providers", response_model=list[EvidenceProviderRead])
def providers() -> list[dict]:
    return list_evidence_providers()


@router.post("/analysis-runs/{run_id}/evidence")
def annotate(
    run_id: str,
    payload: EvidenceAnnotateRequest | None = None,
    db: Session = Depends(get_db),
) -> dict:
    run = _get_run(db, run_id)
    payload = payload or EvidenceAnnotateRequest()
    try:
        return evidence_service.annotate_run(
            db,
            run,
            provider_names=payload.providers,
            variant_ids=payload.variant_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/analysis-runs/{run_id}/evidence", response_model=list[EvidenceRecordRead])
def list_records(
    run_id: str,
    variant_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list:
    _get_run(db, run_id)
    return evidence_service.list_evidence(db, run_id, variant_id)
