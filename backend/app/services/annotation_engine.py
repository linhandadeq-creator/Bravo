"""Annotation engine: run a provider over a run's variants and persist results.

Every persisted annotation carries full provenance (provider, provider version,
reference build, annotation version, transcript source, timestamp, parameters,
input hash). A provider failure is recorded as ``FAILED`` and never rewritten to
``UNKNOWN``.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.annotation.base import (
    AnnotationStatus,
    ProviderUnavailableError,
    ReferenceContext,
    UnknownProviderError,
)
from app.annotation.reference import validate_compatibility
from app.annotation.registry import get_annotator
from app.models.analysis_run import AnalysisRun
from app.models.annotation import AnnotationRun, VariantAnnotation
from app.models.variant import Variant


class AnnotationGateError(RuntimeError):
    """Raised when variants are not permitted into the Neoantigen Engine."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _variant_label(variant: Variant) -> str:
    chrom = variant.chromosome_normalized or variant.chromosome or "?"
    return f"{chrom}:{variant.position}:{variant.reference}>{variant.alternate}"


def _batch_hash(variants: list[Variant], provider: str, build: str | None) -> str:
    digest = hashlib.sha256()
    digest.update(f"{provider}|{build or 'unknown'}".encode())
    for variant in sorted(variants, key=lambda v: _variant_label(v)):
        digest.update(_variant_label(variant).encode())
    return digest.hexdigest()


def _record_hash(provider: str, version: str | None, build: str | None, label: str) -> str:
    return hashlib.sha256(
        f"{provider}|{version or 'unknown'}|{build or 'unknown'}|{label}".encode()
    ).hexdigest()


def _unique_valid_variants(db: Session, analysis_run_id: str) -> list[Variant]:
    statement = (
        select(Variant)
        .where(
            Variant.analysis_run_id == analysis_run_id,
            Variant.is_valid.is_(True),
            Variant.is_duplicate.is_(False),
        )
        .order_by(
            Variant.sample_role, Variant.chromosome_normalized, Variant.position
        )
    )
    return list(db.execute(statement).scalars().all())


def run_annotation(
    db: Session,
    run: AnalysisRun,
    provider_name: str,
    parameters: dict | None = None,
) -> AnnotationRun:
    parameters = parameters or {}
    started = _now()

    annotation_run = AnnotationRun(
        analysis_run_id=run.id,
        provider=provider_name,
        reference_build=run.reference_build,
        status=AnnotationStatus.FAILED.value,
        parameters=parameters,
        started_at=started,
    )
    db.add(annotation_run)
    db.flush()

    variants = _unique_valid_variants(db, run.id)
    annotation_run.variant_count = len(variants)

    try:
        provider = get_annotator(provider_name, reference_build=run.reference_build)
    except UnknownProviderError as exc:
        annotation_run.status = AnnotationStatus.FAILED.value
        annotation_run.error_message = str(exc)
        annotation_run.finished_at = _now()
        db.commit()
        db.refresh(annotation_run)
        return annotation_run

    metadata = provider.metadata()
    annotation_run.provider_version = metadata.provider_version
    annotation_run.annotation_version = metadata.annotation_version
    annotation_run.transcript_source = metadata.transcript_source
    annotation_run.reference_build = metadata.reference_build

    if not provider.is_available():
        annotation_run.status = AnnotationStatus.UNAVAILABLE.value
        annotation_run.error_message = (
            f"Provider '{provider_name}' is registered but unavailable in this "
            "environment."
        )
        annotation_run.finished_at = _now()
        db.commit()
        db.refresh(annotation_run)
        return annotation_run

    compatibility = validate_compatibility(run.reference_build, metadata)
    annotation_run.compatibility = {
        "ok": compatibility.ok,
        "checks": compatibility.checks,
    }
    if not compatibility.ok:
        annotation_run.status = AnnotationStatus.FAILED.value
        annotation_run.error_message = compatibility.error
        annotation_run.finished_at = _now()
        db.commit()
        db.refresh(annotation_run)
        return annotation_run

    inputs = [
        _to_input(variant)
        for variant in variants
    ]
    annotation_run.input_hash = _batch_hash(
        variants, provider_name, metadata.reference_build
    )

    context = ReferenceContext(
        reference_build=metadata.reference_build,
        transcript_source=metadata.transcript_source,
        annotation_version=metadata.annotation_version,
    )
    # Persist the in-progress annotation run and release the SQLite write lock
    # before the (potentially slow / networked) provider call. Holding a write
    # transaction across annotation would block concurrent writers.
    db.commit()
    try:
        records = provider.annotate(inputs, context)
    except ProviderUnavailableError as exc:
        annotation_run.status = AnnotationStatus.UNAVAILABLE.value
        annotation_run.error_message = str(exc)
        annotation_run.finished_at = _now()
        db.commit()
        db.refresh(annotation_run)
        return annotation_run
    except Exception as exc:  # noqa: BLE001 - provider crash is a hard failure
        annotation_run.status = AnnotationStatus.FAILED.value
        annotation_run.error_message = f"Provider error: {type(exc).__name__}: {exc}"
        annotation_run.finished_at = _now()
        db.commit()
        db.refresh(annotation_run)
        return annotation_run

    by_id = {variant.id: variant for variant in variants}
    counts = {status.value: 0 for status in AnnotationStatus}
    for record in records:
        variant = by_id.get(record.key)
        if variant is None:
            continue
        status_value = record.status
        counts[status_value] = counts.get(status_value, 0) + 1
        db.add(
            VariantAnnotation(
                annotation_run_id=annotation_run.id,
                variant_id=variant.id,
                analysis_run_id=run.id,
                status=status_value,
                consequence=record.consequence,
                impact=record.impact,
                gene=record.gene,
                gene_id=record.gene_id,
                transcript=record.transcript,
                transcript_id=record.transcript_id,
                protein_change=record.protein_change,
                cds_position=record.cds_position,
                protein_position=record.protein_position,
                mutated_peptide=record.mutated_peptide,
                known_variants=(record.extra or {}).get("known_variants"),
                clinical_significance=(record.extra or {}).get("clinical_significance"),
                hgvs_c=(record.extra or {}).get("hgvs_c"),
                hgvs_p=(record.extra or {}).get("hgvs_p"),
                failed_reason=record.failed_reason,
                provider=metadata.provider,
                provider_version=metadata.provider_version,
                reference_build=metadata.reference_build,
                annotation_version=metadata.annotation_version,
                transcript_source=metadata.transcript_source,
                parameters=parameters,
                input_hash=_record_hash(
                    metadata.provider,
                    metadata.provider_version,
                    metadata.reference_build,
                    _variant_label(variant),
                ),
                annotation_timestamp=started,
            )
        )

    annotation_run.annotated_count = counts.get(AnnotationStatus.ANNOTATED.value, 0)
    annotation_run.partial_count = counts.get(AnnotationStatus.PARTIAL.value, 0)
    annotation_run.failed_count = counts.get(AnnotationStatus.FAILED.value, 0)

    if annotation_run.failed_count:
        annotation_run.status = AnnotationStatus.FAILED.value
        annotation_run.error_message = (
            f"{annotation_run.failed_count} variant(s) failed annotation; "
            "results are not downgraded to UNKNOWN."
        )
    elif annotation_run.partial_count:
        annotation_run.status = AnnotationStatus.PARTIAL.value
    elif annotation_run.variant_count == 0:
        annotation_run.status = AnnotationStatus.PARTIAL.value
        annotation_run.error_message = "No unique valid variants to annotate."
    else:
        annotation_run.status = AnnotationStatus.ANNOTATED.value

    annotation_run.finished_at = _now()
    db.commit()
    db.refresh(annotation_run)
    return annotation_run


def _to_input(variant: Variant):
    from app.annotation.base import VariantInput

    return VariantInput(
        key=variant.id,
        chromosome=variant.chromosome_normalized or variant.chromosome,
        position=variant.position,
        reference=variant.reference,
        alternate=variant.alternate,
        variant_type=variant.variant_type,
    )


def latest_annotation_run(db: Session, analysis_run_id: str) -> AnnotationRun | None:
    statement = (
        select(AnnotationRun)
        .where(AnnotationRun.analysis_run_id == analysis_run_id)
        .order_by(AnnotationRun.created_at.desc())
        .limit(1)
    )
    return db.execute(statement).scalars().first()


def require_traceable_annotations(
    db: Session, run: AnalysisRun
) -> tuple[AnnotationRun, dict[str, VariantAnnotation]]:
    """Gate variants entering the Neoantigen Engine.

    Every unique valid variant must carry an annotation whose status is
    ``ANNOTATED`` or ``PARTIAL`` under a successful annotation run. Any
    ``FAILED``/``UNAVAILABLE`` annotation blocks the run.
    """
    from app.services.qc import PASS

    if run.status != PASS:
        raise AnnotationGateError(
            f"Analysis run is {run.status}; only PASS runs may proceed to the "
            "Neoantigen Engine."
        )

    annotation_run = latest_annotation_run(db, run.id)
    if annotation_run is None:
        raise AnnotationGateError(
            "No annotation run exists for this analysis. Annotate the variants "
            "before passing them to the Neoantigen Engine."
        )
    if annotation_run.status in (
        AnnotationStatus.FAILED.value,
        AnnotationStatus.UNAVAILABLE.value,
    ):
        raise AnnotationGateError(
            f"Annotation run is {annotation_run.status}: "
            f"{annotation_run.error_message or 'no detail'}"
        )

    variants = _unique_valid_variants(db, run.id)
    annotations = {
        annotation.variant_id: annotation
        for annotation in db.execute(
            select(VariantAnnotation).where(
                VariantAnnotation.annotation_run_id == annotation_run.id
            )
        )
        .scalars()
        .all()
    }

    missing = [v for v in variants if v.id not in annotations]
    if missing:
        raise AnnotationGateError(
            f"{len(missing)} variant(s) have no annotation and cannot enter the "
            "Neoantigen Engine."
        )
    failed = [
        a
        for a in annotations.values()
        if a.status in (AnnotationStatus.FAILED.value, AnnotationStatus.UNAVAILABLE.value)
    ]
    if failed:
        raise AnnotationGateError(
            f"{len(failed)} annotation(s) are {failed[0].status}; refusing to pass "
            "them downstream."
        )
    return annotation_run, annotations
