"""Combined readiness gate for the Neoantigen Engine.

A run may only proceed when Variant + Annotation + HLA + Expression are all
available. Missing data is reported explicitly and blocks the step; nothing is
fabricated.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun
from app.models.expression import ExpressionRecord
from app.services.annotation_engine import (
    AnnotationGateError,
    require_traceable_annotations,
)
from app.services.expression_service import (
    EXPRESSION_AVAILABLE,
    expression_status,
)
from app.services.hla_service import HLA_AVAILABLE, hla_status
from app.services.qc import PASS


class ReadinessError(RuntimeError):
    pass


def _annotated_genes(db: Session, run: AnalysisRun) -> set[str]:
    try:
        _, annotations = require_traceable_annotations(db, run)
    except AnnotationGateError:
        return set()
    return {
        annotation.gene.upper()
        for annotation in annotations.values()
        if annotation.gene
    }


def _expressed_genes(db: Session, analysis_run_id: str) -> set[str]:
    rows = db.execute(
        select(ExpressionRecord).where(
            ExpressionRecord.analysis_run_id == analysis_run_id,
            ExpressionRecord.is_valid.is_(True),
        )
    ).scalars().all()
    genes = set()
    for row in rows:
        for value in (row.gene_symbol, row.gene_id):
            if value:
                genes.add(value.upper())
    return genes


def integration_status(db: Session, run: AnalysisRun) -> dict:
    hla = hla_status(db, run)
    expression = expression_status(db, run)

    annotated_genes = _annotated_genes(db, run)
    expressed_genes = _expressed_genes(db, run.id)
    linked = annotated_genes & expressed_genes
    missing_expression = sorted(annotated_genes - expressed_genes)

    checks = [
        {
            "id": "hla",
            "label": "HLA",
            "status": "pass" if hla["status"] == HLA_AVAILABLE else "fail",
            "detail": hla["message"],
        },
        {
            "id": "expression",
            "label": "Expression",
            "status": "pass" if expression["status"] == EXPRESSION_AVAILABLE else "fail",
            "detail": expression["message"],
        },
    ]

    ready = all(check["status"] == "pass" for check in checks)
    return {
        "analysis_run_id": run.id,
        "hla": hla,
        "expression": expression,
        "annotated_genes": sorted(annotated_genes),
        "expressed_genes": sorted(expressed_genes),
        "linked_genes": sorted(linked),
        "genes_without_expression": missing_expression,
        "checks": checks,
        "status": "READY" if ready else "BLOCKED",
    }


def require_neoantigen_readiness(db: Session, run: AnalysisRun) -> dict:
    errors: list[str] = []

    if run.status != PASS:
        errors.append(f"Analysis run is {run.status}; a PASS run is required.")

    try:
        require_traceable_annotations(db, run)
    except AnnotationGateError as exc:
        errors.append(str(exc))

    hla = hla_status(db, run)
    if hla["status"] != HLA_AVAILABLE:
        errors.append(f"HLA status is {hla['status']}: {hla['message']}")

    expression = expression_status(db, run)
    if expression["status"] != EXPRESSION_AVAILABLE:
        errors.append(
            f"Expression status is {expression['status']}: {expression['message']}"
        )

    if errors:
        raise ReadinessError(" ".join(errors))

    return integration_status(db, run)
