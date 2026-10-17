from app.services.somatic import (
    NORMAL_ONLY,
    SHARED,
    TUMOR_ONLY,
    UNCERTAIN,
    compare_variants,
)
from app.services.synthetic import EXPECTED_SYNTHETIC
from app.services.vcf_parser import parse_vcf


def _compare(dataset):
    tumor = parse_vcf(dataset.tumor_path, role="TUMOR")
    normal = parse_vcf(dataset.normal_path, role="NORMAL")
    return compare_variants(
        tumor.unique_valid_variants(),
        normal.unique_valid_variants(),
        min_depth=10,
        min_af=0.05,
    )


def test_tumor_normal_matching_counts(synthetic_dataset):
    result = _compare(synthetic_dataset)

    assert result.counts[TUMOR_ONLY] == EXPECTED_SYNTHETIC["somatic"]["TUMOR_ONLY"]
    assert result.counts[NORMAL_ONLY] == EXPECTED_SYNTHETIC["somatic"]["NORMAL_ONLY"]
    assert result.counts[SHARED] == EXPECTED_SYNTHETIC["somatic"]["SHARED"]
    assert result.counts[UNCERTAIN] == EXPECTED_SYNTHETIC["somatic"]["UNCERTAIN"]


def test_tumor_only_is_marked_as_candidate_not_confirmed(synthetic_dataset):
    result = _compare(synthetic_dataset)
    tumor_only = next(c for c in result.candidates if c.classification == TUMOR_ONLY)

    assert "not confirmed" in tumor_only.note.lower()
    assert tumor_only.normal_allele_frequency is None


def test_shared_uses_normalized_chromosome_across_naming_styles(synthetic_dataset):
    result = _compare(synthetic_dataset)
    shared = [c for c in result.candidates if c.classification == SHARED]

    # chr1:1000 is written as "1" in the normal file and "chr1" in the tumor file.
    matched = [c for c in shared if c.chromosome == "chr1" and c.position == 1000]
    assert matched
    assert matched[0].normal_allele_frequency is not None


def test_weak_normal_evidence_is_uncertain(synthetic_dataset):
    result = _compare(synthetic_dataset)
    uncertain = next(c for c in result.candidates if c.classification == UNCERTAIN)

    assert uncertain.position == 9000
    assert uncertain.normal_depth == 3
