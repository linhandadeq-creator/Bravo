"""Variant evidence service: population frequency / known-driver /
clinical-significance annotation over a run's QC'd variants.

Providers are pluggable (mock / gnomad / clinvar / cosmic). Every lookup is
stored with full provenance; failures are recorded as FAILED records and
surfaced — a real provider's failure is never masked by mock data.
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import run_write_with_retry

from app.evidence.base import (
    EvidenceQuery,
    EvidenceStatus,
    EvidenceUnavailableError,
    VariantEvidenceProvider,
)
from app.evidence.registry import (
    UnknownEvidenceProviderError,
    available_evidence_providers,
    get_evidence_provider,
)
from app.models.analysis_run import AnalysisRun
from app.models.variant import Variant
from app.models.variant_evidence import VariantEvidenceRecord


def _tumor_variants(db: Session, run_id: str, variant_ids: list[str] | None) -> list[Variant]:
    statement = (
        select(Variant)
        .where(
            Variant.analysis_run_id == run_id,
            Variant.sample_role == "TUMOR",
            Variant.is_valid.is_(True),
            Variant.is_duplicate.is_(False),
        )
        .order_by(Variant.chromosome_normalized, Variant.position)
    )
    variants = list(db.execute(statement).scalars().all())
    if variant_ids:
        wanted = set(variant_ids)
        variants = [v for v in variants if v.id in wanted]
    return variants


def _resolve_providers(provider_names: list[str] | None) -> list[VariantEvidenceProvider]:
    if not provider_names:
        return available_evidence_providers()
    providers: list[VariantEvidenceProvider] = []
    for name in provider_names:
        providers.append(get_evidence_provider(name))
    return providers


def _to_query(variant: Variant, build: str | None) -> EvidenceQuery:
    return EvidenceQuery(
        chromosome=variant.chromosome_normalized or variant.chromosome,
        position=variant.position,
        reference=variant.reference,
        alternate=variant.alternate,
        reference_build=build or "GRCh38",
    )


def annotate_run(
    db: Session,
    run: AnalysisRun,
    provider_names: list[str] | None = None,
    variant_ids: list[str] | None = None,
) -> dict:
    variants = _tumor_variants(db, run.id, variant_ids)
    try:
        providers = _resolve_providers(provider_names)
    except UnknownEvidenceProviderError as exc:
        raise ValueError(str(exc)) from exc

    build = run.reference_build or "GRCh38"
    results: list[dict] = []
    failed: list[dict] = []
    skipped: list[dict] = []
    # Evidence lookups can be networked (gnomAD). Compute every result first,
    # with NO write transaction open, then persist in one short commit.
    to_delete: list[str] = []
    to_insert: list[dict] = []

    for provider in providers:
        status = provider.health_check()
        if status not in (EvidenceStatus.MOCK, EvidenceStatus.AVAILABLE):
            skipped.append(
                {
                    "provider": provider.provider_name,
                    "status": status.value,
                    "reason": "Provider not usable on this installation.",
                }
            )
            continue
        for variant in variants:
            existing = db.execute(
                select(VariantEvidenceRecord).where(
                    VariantEvidenceRecord.variant_id == variant.id,
                    VariantEvidenceRecord.provider == provider.provider_name,
                )
            ).scalars().first()
            if existing is not None:
                to_delete.append(existing.id)

            query = _to_query(variant, build)
            try:
                result = provider.query(query)
            except EvidenceUnavailableError as exc:
                failed.append(
                    {
                        "variant_id": variant.id,
                        "provider": provider.provider_name,
                        "reason": str(exc),
                    }
                )
                to_insert.append(
                    {
                        "analysis_run_id": run.id,
                        "variant_id": variant.id,
                        "provider": provider.provider_name,
                        "source": f"{provider.provider_name} (failed lookup)",
                        "provider_version": provider.provider_version,
                        "status": EvidenceStatus.FAILED.value,
                        "detail": {"error": str(exc)},
                    }
                )
                continue
            to_insert.append(
                {
                    "analysis_run_id": run.id,
                    "variant_id": variant.id,
                    "provider": provider.provider_name,
                    "source": result.source,
                    "provider_version": result.provider_version,
                    "status": result.status,
                    "population_frequency": result.population_frequency,
                    "known_driver": result.known_driver,
                    "clinical_significance": result.clinical_significance,
                    "identifiers": result.identifiers,
                    "detail": result.detail,
                }
            )
            results.append(
                {
                    "variant_id": variant.id,
                    "provider": provider.provider_name,
                    "status": result.status,
                    "population_frequency": result.population_frequency,
                    "known_driver": result.known_driver,
                    "clinical_significance": result.clinical_significance,
                }
            )

    def _persist() -> None:
        if to_delete:
            db.execute(
                delete(VariantEvidenceRecord).where(
                    VariantEvidenceRecord.id.in_(to_delete)
                )
            )
        for spec in to_insert:
            db.add(VariantEvidenceRecord(**spec))
        db.flush()

    run_write_with_retry(db, _persist)
    return {
        "analysis_run_id": run.id,
        "reference_build": build,
        "variants_considered": len(variants),
        "records_written": len(results),
        "providers": [p.provider_name for p in providers],
        "skipped_providers": skipped,
        "failed_lookups": failed,
        "results": results,
    }


def list_evidence(db: Session, run_id: str, variant_id: str | None = None) -> list[VariantEvidenceRecord]:
    statement = (
        select(VariantEvidenceRecord)
        .where(VariantEvidenceRecord.analysis_run_id == run_id)
        .order_by(VariantEvidenceRecord.variant_id, VariantEvidenceRecord.provider)
    )
    if variant_id:
        statement = statement.where(VariantEvidenceRecord.variant_id == variant_id)
    return list(db.execute(statement).scalars().all())


def evidence_for_variant(db: Session, variant_id: str) -> list[VariantEvidenceRecord]:
    statement = (
        select(VariantEvidenceRecord)
        .where(VariantEvidenceRecord.variant_id == variant_id)
        .order_by(VariantEvidenceRecord.provider)
    )
    return list(db.execute(statement).scalars().all())


def clear_evidence(db: Session, run_id: str) -> int:
    result = db.execute(
        delete(VariantEvidenceRecord).where(
            VariantEvidenceRecord.analysis_run_id == run_id
        )
    )
    db.commit()
    return result.rowcount or 0
