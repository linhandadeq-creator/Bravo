"""HLA ingestion, normalization and status."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.hla.normalization import (
    NORMALIZATION_METHOD,
    NORMALIZATION_VERSION,
    normalize_hla_allele,
    parse_hla_records,
)
from app.models.analysis_run import AnalysisRun
from app.models.hla import HLAProfile

HLA_AVAILABLE = "HLA_AVAILABLE"
HLA_UNAVAILABLE = "HLA_UNAVAILABLE"
HLA_INVALID = "HLA_INVALID"


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def parse_and_ingest(
    db: Session,
    run: AnalysisRun,
    content: str,
    fmt: str,
    source: str | None,
    method: str | None,
    version: str | None,
) -> list[HLAProfile]:
    records = parse_hla_records(content, fmt)
    return ingest_records(
        db, run, records, source=source, method=method, version=version,
        input_hash=hash_content(content),
    )


def ingest_records(
    db: Session,
    run: AnalysisRun,
    records: list[dict],
    source: str | None,
    method: str | None,
    version: str | None,
    input_hash: str | None = None,
) -> list[HLAProfile]:
    now = datetime.now(timezone.utc)
    seen: set[tuple[str, str]] = set()
    profiles: list[HLAProfile] = []

    for record in records:
        result = normalize_hla_allele(record.get("allele"), record.get("declared_class"))
        is_duplicate = False
        if result.valid and result.normalized and result.allele_class:
            key = (result.normalized, result.allele_class)
            if key in seen:
                is_duplicate = True
            else:
                seen.add(key)

        profile = HLAProfile(
            analysis_run_id=run.id,
            allele=result.normalized,
            allele_raw=record.get("allele"),
            allele_class=result.allele_class or record.get("declared_class"),
            locus=result.locus,
            source=record.get("source") or source,
            method=record.get("method") or method,
            confidence=record.get("confidence"),
            version=record.get("version") or version,
            is_valid=result.valid,
            is_duplicate=is_duplicate,
            invalid_reason=result.reason,
            normalization_method=NORMALIZATION_METHOD,
            input_hash=input_hash,
            timestamp=now,
        )
        db.add(profile)
        profiles.append(profile)

    db.commit()
    for profile in profiles:
        db.refresh(profile)
    return profiles


def list_profiles(db: Session, analysis_run_id: str) -> list[HLAProfile]:
    statement = (
        select(HLAProfile)
        .where(HLAProfile.analysis_run_id == analysis_run_id)
        .order_by(HLAProfile.allele_class, HLAProfile.locus, HLAProfile.allele)
    )
    return list(db.execute(statement).scalars().all())


def hla_status(db: Session, run: AnalysisRun) -> dict:
    profiles = list_profiles(db, run.id)
    if not profiles:
        return {
            "status": HLA_UNAVAILABLE,
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "duplicate": 0,
            "class_i": 0,
            "class_ii": 0,
            "normalization_method": NORMALIZATION_METHOD,
            "normalization_version": NORMALIZATION_VERSION,
            "message": "No HLA data. HLA_UNAVAILABLE — prediction steps depending "
            "on HLA are blocked.",
        }

    invalid = [p for p in profiles if not p.is_valid]
    valid = [p for p in profiles if p.is_valid]
    status = HLA_INVALID if invalid else HLA_AVAILABLE
    non_duplicate_valid = [p for p in valid if not p.is_duplicate]

    message = "HLA data available."
    if invalid:
        details = []
        for profile in invalid[:5]:
            raw = profile.allele_raw if profile.allele_raw not in (None, "") else "(empty)"
            details.append(f"{raw}: {profile.invalid_reason or 'invalid'}")
        more = "" if len(invalid) <= 5 else f" (+{len(invalid) - 5} more)"
        message = (
            "Invalid HLA allele(s) present; prediction is blocked. "
            + "; ".join(details)
            + more
        )

    return {
        "status": status,
        "total": len(profiles),
        "valid": len(valid),
        "invalid": len(invalid),
        "duplicate": sum(1 for p in profiles if p.is_duplicate),
        "class_i": sum(1 for p in non_duplicate_valid if p.allele_class == "I"),
        "class_ii": sum(1 for p in non_duplicate_valid if p.allele_class == "II"),
        "normalization_method": NORMALIZATION_METHOD,
        "normalization_version": NORMALIZATION_VERSION,
        "message": message,
    }
