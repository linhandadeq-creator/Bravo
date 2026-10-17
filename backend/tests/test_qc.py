from app.services.qc import BLOCKED, FAILED, PASS, evaluate_qc
from app.services.synthetic import EXPECTED_SYNTHETIC
from app.services.vcf_parser import parse_vcf


def _parse_pair(dataset):
    tumor = parse_vcf(dataset.tumor_path, role="TUMOR")
    normal = parse_vcf(dataset.normal_path, role="NORMAL")
    return tumor, normal


def test_duplicate_detection(synthetic_dataset):
    tumor = parse_vcf(synthetic_dataset.tumor_path, role="TUMOR")
    assert tumor.duplicate_count == EXPECTED_SYNTHETIC["tumor"]["duplicate_variants"]

    duplicate = next(r for r in tumor.records if r.is_duplicate)
    original = next(
        r
        for r in tumor.records
        if r.is_valid and not r.is_duplicate and r.key == duplicate.key
    )
    assert original is not None


def test_invalid_variant_detection(synthetic_dataset):
    tumor = parse_vcf(synthetic_dataset.tumor_path, role="TUMOR")
    reasons = [r.invalid_reason for r in tumor.records if not r.is_valid]

    assert any("symbolic" in (reason or "") for reason in reasons)
    assert any("malformed" in (reason or "") for reason in reasons)


def test_chromosome_normalization(synthetic_dataset):
    normal = parse_vcf(synthetic_dataset.normal_path, role="NORMAL")

    assert normal.normalization_count >= 1
    record = next(
        r for r in normal.records if r.position == 1000 and r.is_valid
    )
    assert record.chromosome == "1"
    assert record.chromosome_normalized == "chr1"
    assert record.chromosome_changed is True


def test_qc_passes_for_matching_builds(synthetic_dataset):
    tumor, normal = _parse_pair(synthetic_dataset)

    qc = evaluate_qc(tumor, normal, "GRCh38", "GRCh38", "GRCh38")

    assert qc.status == PASS
    assert qc.summary["raw_variants"] == (
        EXPECTED_SYNTHETIC["tumor"]["raw_variants"]
        + EXPECTED_SYNTHETIC["normal"]["raw_variants"]
    )
    assert qc.summary["duplicate_variants"] == 1
    assert qc.summary["chromosome_normalizations"] >= 1


def test_reference_build_mismatch_fails(synthetic_dataset):
    tumor, normal = _parse_pair(synthetic_dataset)

    qc = evaluate_qc(tumor, normal, "GRCh38", "GRCh38", "GRCh37")

    assert qc.status == FAILED
    assert "mismatch" in (qc.error_message or "").lower()
    assert "Tumor=GRCh38" in (qc.error_message or "")
    assert "Normal=GRCh37" in (qc.error_message or "")


def test_missing_normal_is_blocked(synthetic_dataset):
    tumor, _ = _parse_pair(synthetic_dataset)

    qc = evaluate_qc(tumor, None, "GRCh38", "GRCh38", None)

    assert qc.status == BLOCKED
    assert "Normal VCF is required" in (qc.error_message or "")


def test_missing_reference_build_is_blocked(synthetic_dataset):
    tumor, normal = _parse_pair(synthetic_dataset)

    qc = evaluate_qc(tumor, normal, None, None, None)

    assert qc.status == BLOCKED
    assert "Reference build is required" in (qc.error_message or "")


def test_unparseable_vcf_is_blocked(tmp_path):
    bad = tmp_path / "broken.vcf"
    bad.write_text("this is not a vcf\njust some text\n")

    result = parse_vcf(str(bad), role="TUMOR")

    assert result.format_ok is False
    assert result.errors
