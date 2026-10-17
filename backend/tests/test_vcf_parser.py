import pytest

from app.services.synthetic import EXPECTED_SYNTHETIC
from app.services.vcf_parser import parse_vcf


def test_parse_gzipped_tumor_vcf(synthetic_dataset):
    result = parse_vcf(synthetic_dataset.tumor_path, role="TUMOR")

    assert result.file_ok is True
    assert result.format_ok is True
    assert result.raw_count == EXPECTED_SYNTHETIC["tumor"]["raw_variants"]
    assert result.valid_count == EXPECTED_SYNTHETIC["tumor"]["valid_variants"]
    assert result.invalid_count == EXPECTED_SYNTHETIC["tumor"]["invalid_variants"]
    assert result.malformed_count == EXPECTED_SYNTHETIC["tumor"]["malformed_records"]


def test_parse_plain_normal_vcf(synthetic_dataset):
    result = parse_vcf(synthetic_dataset.normal_path, role="NORMAL")

    assert result.file_ok is True
    assert result.format_ok is True
    assert result.raw_count == EXPECTED_SYNTHETIC["normal"]["raw_variants"]
    assert result.valid_count == EXPECTED_SYNTHETIC["normal"]["valid_variants"]


def test_extracts_quality_depth_af_and_genotype(synthetic_dataset):
    result = parse_vcf(synthetic_dataset.tumor_path, role="TUMOR")
    record = next(
        r
        for r in result.records
        if r.position == 1000 and r.is_valid and not r.is_duplicate
    )

    assert record.chromosome == "chr1"
    assert record.reference == "A"
    assert record.alternate == "G"
    assert record.quality == 60.0
    assert record.depth == 60
    assert record.allele_frequency == pytest.approx(0.35)
    assert record.genotype == "0/1"
    assert record.variant_type == "SNV"


def test_malformed_and_invalid_records_are_flagged(synthetic_dataset):
    result = parse_vcf(synthetic_dataset.tumor_path, role="TUMOR")

    malformed = [r for r in result.records if r.is_malformed]
    invalid = [r for r in result.records if not r.is_valid]

    assert len(malformed) == 1
    assert "malformed record" in malformed[0].invalid_reason
    assert any("symbolic" in (r.invalid_reason or "") for r in invalid)


def test_pure_python_fallback_matches_pysam(synthetic_dataset, monkeypatch):
    monkeypatch.setattr("app.services.vcf_parser.pysam", None)
    result = parse_vcf(synthetic_dataset.tumor_path, role="TUMOR")

    assert result.file_ok is True
    assert result.format_ok is True
    assert result.raw_count == EXPECTED_SYNTHETIC["tumor"]["raw_variants"]
    assert result.valid_count == EXPECTED_SYNTHETIC["tumor"]["valid_variants"]

    record = next(
        r
        for r in result.records
        if r.position == 1000 and r.is_valid and not r.is_duplicate
    )
    assert record.chromosome == "chr1"
    assert record.reference == "A"
    assert record.alternate == "G"
    assert record.quality == pytest.approx(60.0)
    assert record.depth == 60
    assert record.allele_frequency == pytest.approx(0.35)
    assert record.genotype == "0/1"
    assert record.variant_type == "SNV"
