"""Benchmark against well-known GRCh38 cancer hotspots.

Serves as a small reference set: real coordinates that must annotate to the
expected gene + protein change. Skipped when the offline reference is absent.
"""
from pathlib import Path

import pytest

from app.annotation.base import ReferenceContext, VariantInput
from app.annotation.offline import OfflineAnnotator

_REF = Path(__file__).resolve().parents[1] / "storage" / "reference" / "GRCh38"
_READY = (_REF / "Homo_sapiens.GRCh38.112.gtf.gz").exists() and (
    _REF / "Homo_sapiens.GRCh38.cds.all.fa.gz"
).exists()

# (chrom, pos, ref, alt, expected gene, expected protein change)
HOTSPOTS = [
    ("chr7", 140753336, "A", "T", "BRAF", "p.V600E"),
    ("chr7", 55191822, "T", "G", "EGFR", "p.L858R"),
    ("chr12", 25245350, "C", "T", "KRAS", "p.G12D"),
    ("chr3", 179234297, "A", "G", "PIK3CA", "p.H1047R"),
    ("chr17", 7675088, "C", "T", "TP53", "p.R175H"),
]


@pytest.mark.skipif(not _READY, reason="offline GRCh38 reference not installed")
@pytest.mark.parametrize("chrom,pos,ref,alt,gene,change", HOTSPOTS)
def test_known_hotspot_annotation(chrom, pos, ref, alt, gene, change, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "OFFLINE_REFERENCE_DIR", str(_REF.parent)
    )
    annotator = OfflineAnnotator(reference_build="GRCh38")
    [record] = annotator.annotate(
        [VariantInput(key="x", chromosome=chrom, position=pos, reference=ref, alternate=alt)],
        ReferenceContext(reference_build="GRCh38"),
    )
    assert record.gene == gene
    assert record.protein_change == change
    assert record.mutated_peptide
