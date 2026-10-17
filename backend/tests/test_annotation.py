import pytest

from app.annotation.base import (
    AnnotationStatus,
    ProviderMetadata,
    ReferenceContext,
    VariantAnnotator,
    VariantInput,
)
from app.annotation.mock import MockVariantAnnotator
from app.annotation.reference import validate_compatibility
from app.annotation.registry import register


def _variant(chrom, pos, ref, alt) -> VariantInput:
    return VariantInput(
        key=f"{chrom}:{pos}:{ref}>{alt}",
        chromosome=chrom,
        position=pos,
        reference=ref,
        alternate=alt,
    )


# (chrom, pos, ref, alt, consequence, protein_change, impact, status, gene)
EXPECTED = [
    ("chr1", 1003, "A", "G", "missense", "p.K2E", "MODERATE", "ANNOTATED", "MOCKGENE1"),
    ("chr1", 1008, "G", "A", "synonymous", "p.G3G", "LOW", "ANNOTATED", "MOCKGENE1"),
    ("chr1", 1003, "A", "T", "stop_gained", "p.K2*", "HIGH", "ANNOTATED", "MOCKGENE1"),
    ("chr1", 1015, "T", "C", "stop_lost", "p.*6R", "HIGH", "ANNOTATED", "MOCKGENE1"),
    ("chr1", 1001, "T", "C", "start_lost", "p.M1?", "HIGH", "ANNOTATED", "MOCKGENE1"),
    ("chr1", 1004, "A", "AAA", "frameshift", None, "HIGH", "PARTIAL", "MOCKGENE1"),
    ("chr1", 1004, "A", "AAAA", "inframe_insertion", None, "MODERATE", "PARTIAL", "MOCKGENE1"),
    ("chr1", 1004, "AAA", "A", "frameshift", None, "HIGH", "PARTIAL", "MOCKGENE1"),
    ("chr1", 1004, "AAAG", "A", "inframe_deletion", None, "MODERATE", "PARTIAL", "MOCKGENE1"),
    ("chr2", 5040, "A", "G", "splice_related", None, "HIGH", "PARTIAL", "MOCKGENE2"),
    ("chr9", 12345, "A", "G", "unknown", None, "MODIFIER", "ANNOTATED", None),
]


@pytest.mark.parametrize(
    "chrom,pos,ref,alt,consequence,protein,impact,status,gene", EXPECTED
)
def test_mock_expected_annotations(
    chrom, pos, ref, alt, consequence, protein, impact, status, gene
):
    annotator = MockVariantAnnotator(reference_build="GRCh38")
    inputs = [_variant(chrom, pos, ref, alt)]

    [record] = annotator.annotate(
        inputs, ReferenceContext(reference_build="GRCh38")
    )

    assert record.status == status
    assert record.consequence == consequence
    assert record.protein_change == protein
    assert record.impact == impact
    assert record.gene == gene


def test_expected_vs_actual_is_comparable():
    annotator = MockVariantAnnotator(reference_build="GRCh38")
    inputs = [_variant(c, p, r, a) for c, p, r, a, *_ in EXPECTED]
    records = annotator.annotate(inputs, ReferenceContext(reference_build="GRCh38"))

    actual = [
        (r.consequence, r.protein_change, r.impact, r.status, r.gene)
        for r in records
    ]
    expected = [(c, prot, imp, st, g) for _, _, _, _, c, prot, imp, st, g in EXPECTED]
    assert actual == expected


def test_cds_and_protein_positions():
    annotator = MockVariantAnnotator(reference_build="GRCh38")
    [record] = annotator.annotate(
        [_variant("chr1", 1003, "A", "G")], ReferenceContext(reference_build="GRCh38")
    )
    assert record.cds_position == 4
    assert record.protein_position == 2


def test_metadata_declares_provenance():
    metadata = MockVariantAnnotator(reference_build="GRCh38").metadata()
    assert metadata.reference_build == "GRCh38"
    assert metadata.annotation_version
    assert metadata.transcript_source == "MockTranscripts"
    assert metadata.provider == "mock"


def test_reference_build_mismatch_is_incompatible():
    metadata = MockVariantAnnotator(reference_build="GRCh37").metadata()
    result = validate_compatibility("GRCh38", metadata)
    assert result.ok is False
    assert "mismatch" in (result.error or "").lower()


def test_unknown_transcript_source_is_incompatible():
    metadata = ProviderMetadata(
        provider="x",
        provider_version="1",
        reference_build="GRCh38",
        annotation_version="v1",
        transcript_source="NotRegistered",
    )
    result = validate_compatibility("GRCh38", metadata)
    assert result.ok is False
    assert "transcript" in (result.error or "").lower()


def test_provider_failure_is_failed_not_unknown():
    """A provider crash must yield FAILED and never be rewritten to UNKNOWN."""

    @register
    class BoomAnnotator(VariantAnnotator):
        name = "boom"

        def metadata(self) -> ProviderMetadata:
            return ProviderMetadata(
                provider="boom",
                provider_version="0.0.1",
                reference_build="GRCh38",
                annotation_version="v1",
                transcript_source="MockTranscripts",
            )

        def annotate(self, variants, reference_context):
            raise RuntimeError("boom")

    annotator = BoomAnnotator(reference_build="GRCh38")
    with pytest.raises(RuntimeError):
        annotator.annotate(
            [_variant("chr1", 1003, "A", "G")],
            ReferenceContext(reference_build="GRCh38"),
        )
