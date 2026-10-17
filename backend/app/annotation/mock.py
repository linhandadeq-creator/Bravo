"""Deterministic mock annotation provider.

The provider annotates against a small built-in transcript database
(``MockTranscripts``) and a standard genetic code so that
:mod:`tests.test_annotation` can compare expected vs actual consequences and
protein changes without external tools.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.annotation.base import (
    AnnotationRecord,
    AnnotationStatus,
    Consequence,
    Impact,
    ProviderMetadata,
    ReferenceContext,
    VariantAnnotator,
    VariantInput,
)
from app.annotation.registry import register

ANNOTATION_VERSION = "mock-2026.09"
PROVIDER_VERSION = "1.0.0"
TRANSCRIPT_SOURCE = "MockTranscripts"

_BASES = "TCAG"
_AA = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
_CODON_TABLE = {
    a + b + c: _AA[i * 16 + j * 4 + k]
    for i, a in enumerate(_BASES)
    for j, b in enumerate(_BASES)
    for k, c in enumerate(_BASES)
}


def translate(codon: str) -> str:
    return _CODON_TABLE.get(codon.upper(), "X")


@dataclass(frozen=True)
class MockTranscript:
    gene: str
    gene_id: str
    transcript: str
    transcript_id: str
    chromosome: str
    region_start: int
    region_end: int
    cds_start: int
    cds_sequence: str
    splice_sites: tuple[int, ...] = ()


# ATG AAA GGG TTT CCC TGA  ->  M K G F P *
_MOCK_CDS_1 = "ATGAAAGGGTTTCCCTGA"
# ATG CCC GGG AAA TTT TGA  ->  M P G K F *
_MOCK_CDS_2 = "ATGCCCGGGAAATTTTGA"

MOCK_TRANSCRIPTS: tuple[MockTranscript, ...] = (
    MockTranscript(
        gene="MOCKGENE1",
        gene_id="ENSG_MOCK00001",
        transcript="ENST_MOCK00001",
        transcript_id="ENST_MOCK00001.1",
        chromosome="chr1",
        region_start=1000,
        region_end=1100,
        cds_start=1000,
        cds_sequence=_MOCK_CDS_1,
    ),
    MockTranscript(
        gene="MOCKGENE2",
        gene_id="ENSG_MOCK00002",
        transcript="ENST_MOCK00002",
        transcript_id="ENST_MOCK00002.1",
        chromosome="chr2",
        region_start=5000,
        region_end=5100,
        cds_start=5000,
        cds_sequence=_MOCK_CDS_2,
        splice_sites=(5040,),
    ),
)

_IMPACT_BY_CONSEQUENCE = {
    Consequence.FRAMESHIFT.value: Impact.HIGH.value,
    Consequence.STOP_GAINED.value: Impact.HIGH.value,
    Consequence.STOP_LOST.value: Impact.HIGH.value,
    Consequence.START_LOST.value: Impact.HIGH.value,
    Consequence.SPLICE_RELATED.value: Impact.HIGH.value,
    Consequence.MISSENSE.value: Impact.MODERATE.value,
    Consequence.INFRAME_INSERTION.value: Impact.MODERATE.value,
    Consequence.INFRAME_DELETION.value: Impact.MODERATE.value,
    Consequence.SYNONYMOUS.value: Impact.LOW.value,
    Consequence.UNKNOWN.value: Impact.MODIFIER.value,
}


def _find_transcript(chromosome: str | None, position: int | None) -> MockTranscript | None:
    if chromosome is None or position is None:
        return None
    for transcript in MOCK_TRANSCRIPTS:
        if (
            transcript.chromosome == chromosome
            and transcript.region_start <= position <= transcript.region_end
        ):
            return transcript
    return None


def _record(
    variant: VariantInput,
    transcript: MockTranscript | None,
    consequence: str,
    protein_change: str | None,
    status: str,
    cds_position: int | None = None,
    protein_position: int | None = None,
    failed_reason: str | None = None,
) -> AnnotationRecord:
    return AnnotationRecord(
        key=variant.key,
        status=status,
        consequence=consequence,
        impact=_IMPACT_BY_CONSEQUENCE.get(consequence),
        gene=transcript.gene if transcript else None,
        gene_id=transcript.gene_id if transcript else None,
        transcript=transcript.transcript if transcript else None,
        transcript_id=transcript.transcript_id if transcript else None,
        protein_change=protein_change,
        cds_position=cds_position,
        protein_position=protein_position,
        failed_reason=failed_reason,
    )


def _classify_snv(variant: VariantInput, transcript: MockTranscript) -> AnnotationRecord:
    position = variant.position
    assert position is not None
    ref = (variant.reference or "").upper()
    alt = (variant.alternate or "").upper()

    offset = position - transcript.cds_start
    codon_index = offset // 3
    if codon_index < 0 or codon_index * 3 + 3 > len(transcript.cds_sequence):
        return _record(
            variant,
            transcript,
            Consequence.UNKNOWN.value,
            None,
            AnnotationStatus.PARTIAL.value,
        )

    codon_start = codon_index * 3
    codon = transcript.cds_sequence[codon_start : codon_start + 3]
    pos_in_codon = offset % 3

    if codon[pos_in_codon].upper() != ref:
        return _record(
            variant,
            transcript,
            Consequence.UNKNOWN.value,
            None,
            AnnotationStatus.PARTIAL.value,
            failed_reason="REF allele does not match the mock reference sequence",
        )

    new_codon = codon[:pos_in_codon] + alt + codon[pos_in_codon + 1 :]
    aa_ref = translate(codon)
    aa_alt = translate(new_codon)
    number = codon_index + 1
    cds_position = codon_start + pos_in_codon + 1

    if codon_index == 0 and new_codon != "ATG":
        return _record(
            variant,
            transcript,
            Consequence.START_LOST.value,
            "p.M1?",
            AnnotationStatus.ANNOTATED.value,
            cds_position=cds_position,
            protein_position=1,
        )
    if aa_ref != "*" and aa_alt == "*":
        return _record(
            variant,
            transcript,
            Consequence.STOP_GAINED.value,
            f"p.{aa_ref}{number}*",
            AnnotationStatus.ANNOTATED.value,
            cds_position=cds_position,
            protein_position=number,
        )
    if aa_ref == "*" and aa_alt != "*":
        return _record(
            variant,
            transcript,
            Consequence.STOP_LOST.value,
            f"p.*{number}{aa_alt}",
            AnnotationStatus.ANNOTATED.value,
            cds_position=cds_position,
            protein_position=number,
        )
    if aa_ref == aa_alt:
        return _record(
            variant,
            transcript,
            Consequence.SYNONYMOUS.value,
            f"p.{aa_ref}{number}{aa_ref}",
            AnnotationStatus.ANNOTATED.value,
            cds_position=cds_position,
            protein_position=number,
        )
    return _record(
        variant,
        transcript,
        Consequence.MISSENSE.value,
        f"p.{aa_ref}{number}{aa_alt}",
        AnnotationStatus.ANNOTATED.value,
        cds_position=cds_position,
        protein_position=number,
    )


def _classify_indel(variant: VariantInput, transcript: MockTranscript) -> AnnotationRecord:
    ref = variant.reference or ""
    alt = variant.alternate or ""
    delta = len(alt) - len(ref)
    if delta == 0:
        return _record(
            variant,
            transcript,
            Consequence.UNKNOWN.value,
            None,
            AnnotationStatus.PARTIAL.value,
            failed_reason="equal-length substitution is not modelled",
        )
    if delta % 3 != 0:
        consequence = Consequence.FRAMESHIFT.value
    elif delta > 0:
        consequence = Consequence.INFRAME_INSERTION.value
    else:
        consequence = Consequence.INFRAME_DELETION.value
    # Protein-level consequence for indels is not modelled by the mock provider.
    return _record(
        variant,
        transcript,
        consequence,
        None,
        AnnotationStatus.PARTIAL.value,
    )


@register
class MockVariantAnnotator(VariantAnnotator):
    name = "mock"

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider=self.name,
            provider_version=PROVIDER_VERSION,
            reference_build=self.reference_build or "GRCh38",
            annotation_version=ANNOTATION_VERSION,
            transcript_source=TRANSCRIPT_SOURCE,
            description="Deterministic mock transcript database for demos and tests.",
        )

    def is_available(self) -> bool:
        return True

    def annotate(
        self, variants: list[VariantInput], reference_context: ReferenceContext
    ) -> list[AnnotationRecord]:
        records: list[AnnotationRecord] = []
        for variant in variants:
            try:
                records.append(self._annotate_one(variant))
            except Exception as exc:  # noqa: BLE001 - never mask a provider failure
                records.append(
                    AnnotationRecord(
                        key=variant.key,
                        status=AnnotationStatus.FAILED.value,
                        failed_reason=f"{type(exc).__name__}: {exc}",
                    )
                )
        return records

    def _annotate_one(self, variant: VariantInput) -> AnnotationRecord:
        transcript = _find_transcript(variant.chromosome, variant.position)
        if transcript is None:
            return _record(
                variant,
                None,
                Consequence.UNKNOWN.value,
                None,
                AnnotationStatus.ANNOTATED.value,
            )

        if variant.position is not None and any(
            abs(variant.position - site) <= 2 for site in transcript.splice_sites
        ):
            return _record(
                variant,
                transcript,
                Consequence.SPLICE_RELATED.value,
                None,
                AnnotationStatus.PARTIAL.value,
            )

        in_cds = (
            variant.position is not None
            and transcript.cds_start
            <= variant.position
            < transcript.cds_start + len(transcript.cds_sequence)
        )
        ref = variant.reference or ""
        alt = variant.alternate or ""

        if in_cds and len(ref) == 1 and len(alt) == 1:
            return _classify_snv(variant, transcript)
        if in_cds:
            return _classify_indel(variant, transcript)

        return _record(
            variant,
            transcript,
            Consequence.UNKNOWN.value,
            None,
            AnnotationStatus.PARTIAL.value,
        )
