from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.validation import ValidationDataset, ValidationReport
from app.schemas.validation import (
    ValidationDatasetRead,
    ValidationReportDetail,
    ValidationReportRead,
)
from app.validation.engine import run_full_validation

router = APIRouter(tags=["validation"])


@router.post("/validation/run", response_model=ValidationReportDetail)
def run_validation(db: Session = Depends(get_db)) -> ValidationReport:
    return run_full_validation(db)


@router.get("/validation/reports", response_model=list[ValidationReportRead])
def list_reports(
    limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)
) -> list[ValidationReport]:
    statement = (
        select(ValidationReport)
        .order_by(ValidationReport.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(statement).scalars().all())


@router.get("/validation/reports/{report_id}", response_model=ValidationReportDetail)
def get_report(report_id: str, db: Session = Depends(get_db)) -> ValidationReport:
    report = db.get(ValidationReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation report not found")
    return report


@router.get("/validation/datasets", response_model=list[ValidationDatasetRead])
def list_datasets(db: Session = Depends(get_db)) -> list[ValidationDataset]:
    return list(db.execute(select(ValidationDataset)).scalars().all())
