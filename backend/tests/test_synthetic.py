from app.services.qc import PASS, evaluate_qc
from app.services.somatic import compare_variants
from app.services.synthetic import EXPECTED_SYNTHETIC, generate_synthetic_dataset
from app.services.vcf_parser import parse_vcf


def test_synthetic_dataset_expected_result(tmp_path):
    dataset = generate_synthetic_dataset(tmp_path / "synthetic")

    tumor = parse_vcf(dataset.tumor_path, role="TUMOR")
    normal = parse_vcf(dataset.normal_path, role="NORMAL")

    assert tumor.raw_count == EXPECTED_SYNTHETIC["tumor"]["raw_variants"]
    assert tumor.valid_count == EXPECTED_SYNTHETIC["tumor"]["valid_variants"]
    assert tumor.invalid_count == EXPECTED_SYNTHETIC["tumor"]["invalid_variants"]
    assert tumor.duplicate_count == EXPECTED_SYNTHETIC["tumor"]["duplicate_variants"]
    assert tumor.unique_count == EXPECTED_SYNTHETIC["tumor"]["unique_variants"]
    assert normal.unique_count == EXPECTED_SYNTHETIC["normal"]["unique_variants"]

    qc = evaluate_qc(
        tumor,
        normal,
        dataset.reference_build,
        dataset.reference_build,
        dataset.reference_build,
    )
    assert qc.status == PASS

    somatic = compare_variants(
        tumor.unique_valid_variants(),
        normal.unique_valid_variants(),
        min_depth=10,
        min_af=0.05,
    )
    assert somatic.counts == EXPECTED_SYNTHETIC["somatic"]
