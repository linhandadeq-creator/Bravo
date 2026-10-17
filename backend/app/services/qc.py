"""Quality-control evaluation for a tumor/normal VCF pair.

The QC report is explicit: nothing silently falls back to a default. If the
normal VCF, the reference build, or a parseable VCF is missing the run is
marked ``BLOCKED``. A reference-build mismatch between the tumor and normal
samples is a hard ``FAILED``.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from app.core.reference import normalize_reference_build
from app.services.vcf_parser import ParseResult

PASS = "PASS"
FAILED = "FAILED"
BLOCKED = "BLOCKED"

CHECK_PASS = "pass"
CHECK_WARN = "warn"
CHECK_FAIL = "fail"


@dataclass
class Check:
    id: str
    label: str
    status: str
    detail: str


@dataclass
class QcResult:
    status: str
    error_message: str | None
    summary: dict
    checks: list[Check] = field(default_factory=list)


def _reason_counts(result: ParseResult) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for record in result.records:
        if record.is_valid:
            continue
        reason = record.invalid_reason or "unknown"
        if "malformed record" in reason:
            counts["malformed"] += 1
        elif reason.startswith("missing"):
            counts["missing_field"] += 1
        elif "POS" in reason:
            counts["position"] += 1
        elif "unknown chromosome" in reason:
            counts["chromosome"] += 1
        elif "allele" in reason:
            counts["allele"] += 1
        else:
            counts["other"] += 1
    return counts


def _sample_summary(result: ParseResult | None) -> dict | None:
    if result is None:
        return None
    categories = _reason_counts(result)
    return {
        "role": result.role,
        "file_ok": result.file_ok,
        "format_ok": result.format_ok,
        "file_size_bytes": result.file_size_bytes,
        "raw_variants": result.raw_count,
        "valid_variants": result.valid_count,
        "invalid_variants": result.invalid_count,
        "duplicate_variants": result.duplicate_count,
        "unique_variants": result.unique_count,
        "malformed_records": result.malformed_count,
        "missing_field_records": result.missing_field_count,
        "chromosome_normalizations": result.normalization_count,
        "invalid_by_category": dict(categories),
        "errors": list(result.errors),
        "warnings": list(result.warnings),
    }


def evaluate_qc(
    tumor: ParseResult | None,
    normal: ParseResult | None,
    reference_build: str | None,
    tumor_build: str | None,
    normal_build: str | None,
) -> QcResult:
    tumor_build_norm = normalize_reference_build(tumor_build)
    normal_build_norm = normalize_reference_build(normal_build)
    run_build = normalize_reference_build(reference_build) or tumor_build_norm

    checks: list[Check] = []
    blocked: list[str] = []
    failed: list[str] = []

    tumor_summary = _sample_summary(tumor)
    normal_summary = _sample_summary(normal)

    # ---- Hard blockers -----------------------------------------------------
    if tumor is None or not tumor.file_ok:
        blocked.append("Tumor VCF is missing or could not be read.")
    if tumor is not None and not tumor.format_ok:
        blocked.append("Tumor VCF is not a parseable VCF file.")
    if normal is None or not normal.file_ok:
        blocked.append("Normal VCF is required for tumor/normal pairing.")
    if normal is not None and not normal.format_ok:
        blocked.append("Normal VCF is not a parseable VCF file.")
    if run_build is None:
        blocked.append("Reference build is required and must be GRCh37 or GRCh38.")
    if normal is not None and normal.file_ok and normal_build_norm is None:
        blocked.append("Normal sample reference build is required.")

    # ---- Checks ------------------------------------------------------------
    file_integrity_ok = bool(
        tumor and tumor.file_ok and normal and normal.file_ok
    )
    checks.append(
        Check(
            "file_integrity",
            "File integrity",
            CHECK_PASS if file_integrity_ok else CHECK_FAIL,
            "Both VCF files were read successfully."
            if file_integrity_ok
            else "One or more VCF files could not be read.",
        )
    )

    format_ok = bool(tumor and tumor.format_ok and normal and normal.format_ok)
    checks.append(
        Check(
            "vcf_format",
            "VCF format",
            CHECK_PASS if format_ok else CHECK_FAIL,
            "Both files contain a valid #CHROM header."
            if format_ok
            else "A #CHROM header is missing or the file could not be parsed.",
        )
    )

    total_malformed = (tumor.malformed_count if tumor else 0) + (
        normal.malformed_count if normal else 0
    )
    checks.append(
        Check(
            "malformed_records",
            "Malformed records",
            CHECK_PASS if total_malformed == 0 else CHECK_WARN,
            f"{total_malformed} malformed record(s) detected."
            if total_malformed
            else "No malformed records detected.",
        )
    )

    total_missing = (tumor.missing_field_count if tumor else 0) + (
        normal.missing_field_count if normal else 0
    )
    checks.append(
        Check(
            "missing_required_fields",
            "Missing required fields",
            CHECK_PASS if total_missing == 0 else CHECK_WARN,
            f"{total_missing} record(s) with missing required fields."
            if total_missing
            else "All records have the required CHROM/POS/REF/ALT fields.",
        )
    )

    unknown_chrom = sum(
        _reason_counts(r).get("chromosome", 0)
        for r in (tumor, normal)
        if r is not None
    )
    normalizations = (tumor.normalization_count if tumor else 0) + (
        normal.normalization_count if normal else 0
    )
    chrom_status = CHECK_PASS
    chrom_detail = "Chromosome naming is consistent."
    if unknown_chrom:
        chrom_status = CHECK_WARN
        chrom_detail = f"{unknown_chrom} record(s) use an unknown chromosome."
    elif normalizations:
        chrom_status = CHECK_WARN
        chrom_detail = (
            f"{normalizations} chromosome name(s) normalised "
            "(e.g. '1' -> 'chr1')."
        )
    checks.append(Check("chromosome", "Chromosome", chrom_status, chrom_detail))

    bad_positions = sum(
        _reason_counts(r).get("position", 0) for r in (tumor, normal) if r is not None
    )
    checks.append(
        Check(
            "position",
            "Position",
            CHECK_PASS if bad_positions == 0 else CHECK_FAIL,
            f"{bad_positions} record(s) with an invalid POS."
            if bad_positions
            else "All POS values are valid positive integers.",
        )
    )

    bad_alleles = sum(
        _reason_counts(r).get("allele", 0) for r in (tumor, normal) if r is not None
    )
    checks.append(
        Check(
            "ref_alt",
            "REF / ALT",
            CHECK_PASS if bad_alleles == 0 else CHECK_WARN,
            f"{bad_alleles} record(s) with invalid or unsupported alleles."
            if bad_alleles
            else "All REF/ALT alleles are well formed.",
        )
    )

    duplicates = (tumor.duplicate_count if tumor else 0) + (
        normal.duplicate_count if normal else 0
    )
    checks.append(
        Check(
            "duplicates",
            "Duplicate variants",
            CHECK_PASS if duplicates == 0 else CHECK_WARN,
            f"{duplicates} duplicate variant(s) detected and de-duplicated."
            if duplicates
            else "No duplicate variants detected.",
        )
    )

    # ---- Reference build ---------------------------------------------------
    build_status = CHECK_PASS
    build_detail = f"Reference build: {run_build}."
    if run_build is None:
        build_status = CHECK_FAIL
        build_detail = "Reference build is not set."
    elif (
        tumor_build_norm is not None
        and normal_build_norm is not None
        and tumor_build_norm != normal_build_norm
    ):
        build_status = CHECK_FAIL
        build_detail = (
            "Reference build mismatch: "
            f"Tumor={tumor_build_norm}, Normal={normal_build_norm}."
        )
        failed.append(
            "Reference build mismatch between tumor and normal samples "
            f"(Tumor={tumor_build_norm}, Normal={normal_build_norm}). "
            "Analyses across different builds are not allowed."
        )
    elif tumor_build_norm is not None and tumor_build_norm != run_build:
        build_status = CHECK_FAIL
        build_detail = (
            f"Tumor sample build ({tumor_build_norm}) does not match the "
            f"analysis reference build ({run_build})."
        )
        failed.append(build_detail)
    elif normal_build_norm is not None and normal_build_norm != run_build:
        build_status = CHECK_FAIL
        build_detail = (
            f"Normal sample build ({normal_build_norm}) does not match the "
            f"analysis reference build ({run_build})."
        )
        failed.append(build_detail)
    checks.append(
        Check("reference_build", "Reference build", build_status, build_detail)
    )

    if tumor is not None and tumor.file_ok and tumor.valid_count and tumor.unique_count == 0:
        failed.append("No unique valid tumor variants remain after QC.")
    if normal is not None and normal.file_ok and normal.valid_count and normal.unique_count == 0:
        failed.append("No unique valid normal variants remain after QC.")

    checks.append(
        Check(
            "normal_present",
            "Normal sample",
            CHECK_PASS if normal is not None and normal.file_ok else CHECK_FAIL,
            "Normal sample present for pairing."
            if normal is not None and normal.file_ok
            else "Normal sample missing; somatic classification is blocked.",
        )
    )

    # ---- Overall status ----------------------------------------------------
    if blocked:
        status = BLOCKED
        error_message = " ".join(blocked)
    elif failed:
        status = FAILED
        error_message = " ".join(failed)
    else:
        status = PASS
        error_message = None

    summary = {
        "status": status,
        "reference_build": run_build,
        "tumor_reference_build": tumor_build_norm,
        "normal_reference_build": normal_build_norm,
        "raw_variants": sum(r.raw_count for r in (tumor, normal) if r is not None),
        "valid_variants": sum(r.valid_count for r in (tumor, normal) if r is not None),
        "invalid_variants": sum(
            r.invalid_count for r in (tumor, normal) if r is not None
        ),
        "duplicate_variants": sum(
            r.duplicate_count for r in (tumor, normal) if r is not None
        ),
        "unique_variants": sum(r.unique_count for r in (tumor, normal) if r is not None),
        "malformed_records": total_malformed,
        "missing_field_records": total_missing,
        "chromosome_normalizations": normalizations,
        "tumor": tumor_summary,
        "normal": normal_summary,
        "checks": [
            {"id": c.id, "label": c.label, "status": c.status, "detail": c.detail}
            for c in checks
        ],
        "errors": blocked + failed,
    }
    return QcResult(status=status, error_message=error_message, summary=summary, checks=checks)
