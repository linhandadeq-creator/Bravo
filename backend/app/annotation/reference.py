"""Reference compatibility between the VCF, annotation build and transcript DB.

The provider declares its ``reference_build``, ``annotation_version`` and
``transcript_source``. Before annotation is accepted the engine checks that the
VCF reference build, the annotation reference build and the transcript database
are all consistent.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.annotation.base import ProviderMetadata

KNOWN_TRANSCRIPT_SOURCES: dict[str, set[str]] = {
    "GRCh38": {"MockTranscripts", "Ensembl", "GENCODE_v44", "RefSeq_GRCh38"},
    "GRCh37": {"MockTranscripts", "Ensembl", "GENCODE_v19", "RefSeq_GRCh37"},
}


@dataclass
class CompatibilityResult:
    ok: bool
    error: str | None = None
    checks: list[dict] = field(default_factory=list)


def validate_compatibility(
    vcf_reference_build: str | None, metadata: ProviderMetadata
) -> CompatibilityResult:
    checks: list[dict] = []
    errors: list[str] = []

    def check(identifier: str, label: str, ok: bool, detail: str) -> None:
        checks.append(
            {
                "id": identifier,
                "label": label,
                "status": "pass" if ok else "fail",
                "detail": detail,
            }
        )
        if not ok:
            errors.append(detail)

    vcf_ok = bool(vcf_reference_build)
    check(
        "vcf_build",
        "VCF reference build",
        vcf_ok,
        "VCF reference build is set."
        if vcf_ok
        else "VCF reference build is missing; annotation cannot be validated.",
    )

    build_match = bool(vcf_reference_build) and metadata.reference_build == vcf_reference_build
    check(
        "reference_build",
        "Annotation reference build",
        build_match,
        (
            f"Annotation reference build matches the VCF ({metadata.reference_build})."
            if build_match
            else "Reference build mismatch: VCF="
            f"{vcf_reference_build or 'missing'}, "
            f"annotation={metadata.reference_build or 'missing'}."
        ),
    )

    version_ok = bool(metadata.annotation_version)
    check(
        "annotation_version",
        "Annotation version",
        version_ok,
        (
            f"Annotation version {metadata.annotation_version}."
            if version_ok
            else "Annotation version is not declared."
        ),
    )

    transcript_ok = bool(metadata.transcript_source)
    known_sources = KNOWN_TRANSCRIPT_SOURCES.get(metadata.reference_build, set())
    transcript_known = transcript_ok and metadata.transcript_source in known_sources
    check(
        "transcript_source",
        "Transcript database",
        transcript_known,
        (
            f"Transcript source '{metadata.transcript_source}' is registered for "
            f"{metadata.reference_build}."
            if transcript_known
            else (
                "Transcript database is missing or not registered for "
                f"{metadata.reference_build or 'unknown'}: "
                f"'{metadata.transcript_source or 'missing'}'."
            )
        ),
    )

    return CompatibilityResult(ok=not errors, error=" ".join(errors) or None, checks=checks)
