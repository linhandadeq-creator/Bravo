"""Analysis orchestration: parse, QC, compare and persist results.

Parsing and QC run **outside** any database transaction so the SQLite writer
lock is only held for the short persistence step (not across VCF parsing).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import run_write_with_retry
from app.models.analysis_run import MODE_SYNTHETIC, MODE_UPLOAD, AnalysisRun
from app.models.sample import Sample
from app.models.somatic_candidate import SomaticCandidate
from app.models.variant import Variant
from app.services.qc import PASS, evaluate_qc
from app.services.somatic import compare_variants
from app.services.uploads import copy_limited
from app.services.vcf_parser import ParseResult, parse_vcf


def _storage_dir(*parts: str) -> Path:
    directory = settings.storage_path.joinpath(*parts)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_upload(
    fileobj, project_id: str, filename: str | None, prefix: str
) -> tuple[str, int]:
    directory = _storage_dir("uploads", project_id)
    safe_name = Path(filename or "upload.vcf").name
    destination = directory / f"{prefix}_{safe_name}"
    size = copy_limited(fileobj, destination)
    return str(destination), size


def _persist_variants(
    db: Session, run: AnalysisRun, parsed: ParseResult | None, sample: Sample | None
) -> None:
    if parsed is None:
        return
    for record in parsed.records:
        db.add(
            Variant(
                analysis_run_id=run.id,
                sample_id=sample.id if sample else None,
                sample_role=parsed.role,
                line_number=record.line_number,
                chromosome=record.chromosome,
                chromosome_normalized=record.chromosome_normalized,
                chromosome_normalized_flag=record.chromosome_changed,
                position=record.position,
                reference=record.reference,
                alternate=record.alternate,
                quality=record.quality,
                filter=record.filter,
                depth=record.depth,
                allele_frequency=record.allele_frequency,
                genotype=record.genotype,
                variant_type=record.variant_type,
                record_id=record.record_id,
                info=record.info,
                format_fields=record.format_fields,
                is_valid=record.is_valid,
                is_duplicate=record.is_duplicate,
                is_malformed=record.is_malformed,
                invalid_reason=record.invalid_reason,
            )
        )


def _sample_template(sample: Sample | None) -> dict | None:
    """Capture a sample's field values so it can be recreated on retry."""
    if sample is None:
        return None
    return {
        "obj": sample,
        "fields": {
            "id": sample.id,
            "project_id": sample.project_id,
            "name": sample.name,
            "sample_type": sample.sample_type,
            "reference_build": sample.reference_build,
            "original_filename": sample.original_filename,
            "storage_path": sample.storage_path,
            "file_size_bytes": sample.file_size_bytes,
            "source": sample.source,
        },
    }


def _materialize_sample(db: Session, template: dict | None) -> Sample | None:
    if template is None:
        return None
    original: Sample = template["obj"]
    if sa_inspect(original).persistent:
        return original
    # Transient (newly built) sample: recreate from the captured fields so a
    # retried transaction after a rollback inserts a fresh object. Assign an
    # explicit id (column defaults are not applied until flush) so callers and
    # the foreign keys can reference it before the insert.
    fields = dict(template["fields"])
    if not fields.get("id"):
        fields["id"] = str(uuid.uuid4())
    return Sample(**fields)


def run_analysis(
    db: Session,
    *,
    project_id: str,
    tumor_sample: Sample | None,
    normal_sample: Sample | None,
    reference_build: str | None,
    mode: str = MODE_UPLOAD,
) -> AnalysisRun:
    # ---- parse + QC: no database transaction is open here ----
    tumor_parsed = (
        parse_vcf(tumor_sample.storage_path, role="TUMOR")
        if tumor_sample and tumor_sample.storage_path
        else None
    )
    normal_parsed = (
        parse_vcf(normal_sample.storage_path, role="NORMAL")
        if normal_sample and normal_sample.storage_path
        else None
    )

    qc = evaluate_qc(
        tumor_parsed,
        normal_parsed,
        reference_build,
        tumor_sample.reference_build if tumor_sample else None,
        normal_sample.reference_build if normal_sample else None,
    )

    candidate_specs: list[dict] = []
    if qc.status == PASS:
        somatic = compare_variants(
            tumor_parsed.unique_valid_variants() if tumor_parsed else [],
            normal_parsed.unique_valid_variants() if normal_parsed else [],
            settings.MIN_DEPTH_FOR_CONFIDENT,
            settings.MIN_ALLELE_FREQUENCY_FOR_CONFIDENT,
        )
        qc.summary["somatic"] = somatic.counts
        candidate_specs = [
            {
                "chromosome": c.chromosome,
                "position": c.position,
                "reference": c.reference,
                "alternate": c.alternate,
                "classification": c.classification,
                "tumor_allele_frequency": c.tumor_allele_frequency,
                "normal_allele_frequency": c.normal_allele_frequency,
                "tumor_depth": c.tumor_depth,
                "normal_depth": c.normal_depth,
                "tumor_genotype": c.tumor_genotype,
                "normal_genotype": c.normal_genotype,
                "note": c.note,
            }
            for c in somatic.candidates
        ]

    tumor_template = _sample_template(tumor_sample)
    normal_template = _sample_template(normal_sample)

    def _persist() -> AnalysisRun:
        # Short write unit: only inserts, re-runnable after a lock rollback.
        tumor = _materialize_sample(db, tumor_template)
        normal = _materialize_sample(db, normal_template)
        for sample in (tumor, normal):
            if sample is not None and sa_inspect(sample).transient:
                db.add(sample)

        run = AnalysisRun(
            id=str(uuid.uuid4()),
            project_id=project_id,
            tumor_sample_id=tumor.id if tumor else None,
            normal_sample_id=normal.id if normal else None,
            reference_build=qc.summary.get("reference_build"),
            status=qc.status,
            mode=mode,
            error_message=qc.error_message,
            qc_summary=qc.summary,
            somatic_summary=qc.summary.get("somatic"),
            finished_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.flush()

        _persist_variants(db, run, tumor_parsed, tumor)
        _persist_variants(db, run, normal_parsed, normal)
        for spec in candidate_specs:
            db.add(SomaticCandidate(analysis_run_id=run.id, **spec))
        db.flush()
        return run

    run = run_write_with_retry(db, _persist)
    db.refresh(run)
    return run


def new_synthetic_directory() -> Path:
    return _storage_dir("synthetic", uuid.uuid4().hex)
