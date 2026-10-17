"""Expression ingestion, identifier normalization, matrix quantification and status."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.expression.identifiers import (
    GENE_ID_NORMALIZATION_METHOD,
    TRANSCRIPT_ID_NORMALIZATION_METHOD,
    normalize_gene_id,
    normalize_transcript_id,
)
from app.expression.parsing import parse_expression_records
from app.expression.rnaseq import (
    DEFAULT_EXPRESSION_THRESHOLD,
    DEFAULT_LOG2FC_THRESHOLD,
    DEFAULT_PSEUDOCOUNT,
    QUANTIFICATION_METHOD,
    QUANTIFICATION_VERSION,
    parse_expression_matrix,
    quantify,
)
from app.models.analysis_run import AnalysisRun
from app.models.expression import (
    LEVEL_GENE,
    LEVEL_TRANSCRIPT,
    ExpressionQuantification,
    ExpressionRecord,
)

EXPRESSION_AVAILABLE = "EXPRESSION_AVAILABLE"
EXPRESSION_UNAVAILABLE = "EXPRESSION_UNAVAILABLE"
EXPRESSION_INVALID = "EXPRESSION_INVALID"

NORMALIZATION_METHOD = (
    f"{GENE_ID_NORMALIZATION_METHOD}+{TRANSCRIPT_ID_NORMALIZATION_METHOD}"
)
NORMALIZATION_VERSION = "1.0.0"


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def parse_and_ingest(
    db: Session,
    run: AnalysisRun,
    content: str,
    fmt: str,
    source: str | None,
    version: str | None,
    default_unit: str | None = None,
) -> list[ExpressionRecord]:
    records = parse_expression_records(content, fmt)
    return ingest_records(
        db, run, records, source=source, version=version,
        default_unit=default_unit, input_hash=hash_content(content),
    )


def ingest_records(
    db: Session,
    run: AnalysisRun,
    records: list[dict],
    source: str | None,
    version: str | None,
    default_unit: str | None = None,
    input_hash: str | None = None,
) -> list[ExpressionRecord]:
    now = datetime.now(timezone.utc)
    persisted: list[ExpressionRecord] = []

    for record in records:
        gene = normalize_gene_id(record.get("gene_id"), record.get("gene_symbol"))
        transcript = normalize_transcript_id(record.get("transcript_id"))

        raw_value = record.get("expression_value")
        value: float | None
        invalid_reason: str | None = None
        try:
            value = float(raw_value) if raw_value not in (None, "") else None
        except (TypeError, ValueError):
            value = None
            invalid_reason = f"non-numeric expression value '{raw_value}'"

        if value is None and invalid_reason is None:
            invalid_reason = "missing expression value"

        level = (record.get("level") or "").strip().upper() or None
        if level not in (LEVEL_GENE, LEVEL_TRANSCRIPT):
            level = LEVEL_TRANSCRIPT if transcript.normalized else LEVEL_GENE

        symbol = record.get("gene_symbol")
        if not symbol and gene.normalized:
            from app.expression.identifiers import GENE_ID_TO_SYMBOL

            symbol = GENE_ID_TO_SYMBOL.get(gene.normalized)

        row = ExpressionRecord(
            analysis_run_id=run.id,
            level=level,
            gene_id=gene.normalized,
            gene_symbol=symbol.upper() if symbol else None,
            transcript_id=transcript.normalized,
            expression_value=value,
            unit=record.get("unit") or default_unit,
            source=record.get("source") or source,
            raw_gene_id=gene.raw,
            raw_transcript_id=transcript.raw,
            gene_id_changed=gene.changed,
            transcript_id_changed=transcript.changed,
            gene_id_resolved=gene.resolved,
            is_valid=invalid_reason is None,
            invalid_reason=invalid_reason,
            normalization_method=NORMALIZATION_METHOD,
            input_hash=input_hash,
            version=version,
            timestamp=now,
        )
        db.add(row)
        persisted.append(row)

    db.commit()
    for row in persisted:
        db.refresh(row)
    return persisted


def list_records(db: Session, analysis_run_id: str) -> list[ExpressionRecord]:
    statement = (
        select(ExpressionRecord)
        .where(ExpressionRecord.analysis_run_id == analysis_run_id)
        .order_by(ExpressionRecord.level, ExpressionRecord.gene_id, ExpressionRecord.transcript_id)
    )
    return list(db.execute(statement).scalars().all())


def expression_status(db: Session, run: AnalysisRun) -> dict:
    records = list_records(db, run.id)
    if not records:
        return {
            "status": EXPRESSION_UNAVAILABLE,
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "gene_level": 0,
            "transcript_level": 0,
            "normalized_identifiers": 0,
            "normalization_method": NORMALIZATION_METHOD,
            "normalization_version": NORMALIZATION_VERSION,
            "message": "No expression data. EXPRESSION_UNAVAILABLE — expression is "
            "never fabricated and dependent prediction steps are blocked.",
        }

    valid = [r for r in records if r.is_valid]
    invalid = [r for r in records if not r.is_valid]
    status = EXPRESSION_AVAILABLE if valid else EXPRESSION_INVALID

    result = {
        "status": status,
        "total": len(records),
        "valid": len(valid),
        "invalid": len(invalid),
        "gene_level": sum(1 for r in valid if r.level == LEVEL_GENE),
        "transcript_level": sum(1 for r in valid if r.level == LEVEL_TRANSCRIPT),
        "normalized_identifiers": sum(
            1 for r in records if r.gene_id_changed or r.transcript_id_changed
        ),
        "normalization_method": NORMALIZATION_METHOD,
        "normalization_version": NORMALIZATION_VERSION,
        "message": "Expression data available."
        if valid
        else "No valid expression records; dependent prediction is blocked.",
    }
    result["quantification"] = quantification_summary(db, run.id)
    return result


# ------------------------------------------------------- RNA-seq matrix -------


def quantify_matrix(
    db: Session,
    run: AnalysisRun,
    content: str,
    fmt: str,
    tumor_samples: list[str] | None = None,
    normal_samples: list[str] | None = None,
    unit: str | None = None,
    source: str | None = None,
    version: str | None = None,
    pseudocount: float = DEFAULT_PSEUDOCOUNT,
    expression_threshold: float = DEFAULT_EXPRESSION_THRESHOLD,
    log2fc_threshold: float = DEFAULT_LOG2FC_THRESHOLD,
) -> dict:
    """Quantify a tumor/normal expression matrix and persist rows.

    Also ingests the tumor values as ordinary ExpressionRecords so the
    downstream candidate pipeline (tumor expression evidence) keeps working.
    """
    rows, layout = parse_expression_matrix(content, fmt, tumor_samples, normal_samples)
    results = quantify(rows, pseudocount, expression_threshold, log2fc_threshold)
    input_hash = hash_content(content)

    db.execute(
        delete(ExpressionQuantification).where(
            ExpressionQuantification.analysis_run_id == run.id
        )
    )

    record_rows = []
    for result in results:
        gene_id = (result.get("gene_id") or "").strip() or None
        symbol = (result.get("gene_symbol") or "").strip() or None
        if not gene_id and not symbol:
            continue
        record_rows.append(
            {
                "gene_id": gene_id,
                "gene_symbol": symbol,
                "expression_value": result.get("tumor_value"),
                "unit": unit,
                "source": source or QUANTIFICATION_METHOD,
                "level": LEVEL_GENE,
            }
        )
        db.add(
            ExpressionQuantification(
                analysis_run_id=run.id,
                gene_id=gene_id,
                gene_symbol=symbol.upper() if symbol else None,
                tumor_value=result.get("tumor_value"),
                normal_value=result.get("normal_value"),
                log2_fold_change=result.get("log2_fold_change"),
                is_expressed=bool(result.get("is_expressed")),
                differentially_expressed=bool(result.get("differentially_expressed")),
                note=result.get("note"),
                unit=unit,
                method=QUANTIFICATION_METHOD,
                version=version or QUANTIFICATION_VERSION,
                pseudocount=pseudocount,
                expression_threshold=expression_threshold,
                log2fc_threshold=log2fc_threshold,
                samples=layout,
                input_hash=input_hash,
            )
        )

    db.execute(delete(ExpressionRecord).where(ExpressionRecord.analysis_run_id == run.id))
    ingest_records(
        db,
        run,
        record_rows,
        source=source or QUANTIFICATION_METHOD,
        version=version or QUANTIFICATION_VERSION,
        default_unit=unit,
        input_hash=input_hash,
    )
    db.commit()
    return {
        "analysis_run_id": run.id,
        "genes_quantified": len(record_rows),
        "expressed": sum(1 for r in results if r.get("is_expressed")),
        "differentially_expressed": sum(
            1 for r in results if r.get("differentially_expressed")
        ),
        "method": QUANTIFICATION_METHOD,
        "version": QUANTIFICATION_VERSION,
        "pseudocount": pseudocount,
        "expression_threshold": expression_threshold,
        "log2fc_threshold": log2fc_threshold,
        "samples": layout,
    }


def list_quantification(
    db: Session,
    run_id: str,
    differentially_expressed: bool | None = None,
    gene_id: str | None = None,
) -> list[ExpressionQuantification]:
    statement = (
        select(ExpressionQuantification)
        .where(ExpressionQuantification.analysis_run_id == run_id)
        .order_by(
            ExpressionQuantification.differentially_expressed.desc(),
            ExpressionQuantification.log2_fold_change.desc(),
        )
    )
    if differentially_expressed is not None:
        statement = statement.where(
            ExpressionQuantification.differentially_expressed.is_(differentially_expressed)
        )
    if gene_id:
        statement = statement.where(ExpressionQuantification.gene_id == gene_id)
    return list(db.execute(statement).scalars().all())


def quantification_summary(db: Session, run_id: str) -> dict:
    rows = list_quantification(db, run_id)
    if not rows:
        return {
            "status": "QUANTIFICATION_UNAVAILABLE",
            "total": 0,
            "message": "No RNA-seq matrix quantification. Upload a tumor/normal "
            "expression matrix via POST /expression/quantify.",
        }
    return {
        "status": "QUANTIFICATION_AVAILABLE",
        "total": len(rows),
        "expressed": sum(1 for r in rows if r.is_expressed),
        "differentially_expressed": sum(1 for r in rows if r.differentially_expressed),
        "method": rows[0].method,
        "version": rows[0].version,
        "pseudocount": rows[0].pseudocount,
        "expression_threshold": rows[0].expression_threshold,
        "log2fc_threshold": rows[0].log2fc_threshold,
        "message": "RNA-seq matrix quantification available.",
    }
