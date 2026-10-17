from pathlib import Path

import numpy as np
import pytest

from app.annotation.base import ReferenceContext, VariantInput
from app.annotation.offline import (
    OfflineAnnotator,
    _cds_offset,
    _coding_consequence,
    _codon_aa,
    _query_overlaps,
)
from app.annotation.registry import available_provider_names
from app.core.config import settings

# Tests run with STORAGE_DIR pointed at a temp dir, so resolve the real
# reference data from the repository instead of the (patched) storage path.
_REAL_REFERENCE = Path(__file__).resolve().parents[1] / "storage" / "reference"
_REAL_GRCH38 = _REAL_REFERENCE / "GRCh38"
_GRCH38_READY = (
    _REAL_GRCH38 / "Homo_sapiens.GRCh38.112.gtf.gz"
).exists() and (_REAL_GRCH38 / "Homo_sapiens.GRCh38.cds.all.fa.gz").exists()


def _variant(chrom, pos, ref, alt) -> VariantInput:
    return VariantInput(
        key=f"{chrom}:{pos}:{ref}>{alt}",
        chromosome=chrom,
        position=pos,
        reference=ref,
        alternate=alt,
    )


def test_offline_provider_is_registered():
    assert "offline" in available_provider_names()


def test_codon_aa_handles_stop_and_unknown():
    assert _codon_aa("ATG") == "M"
    assert _codon_aa("TAA") == "*"
    assert _codon_aa("TGX") == "X"


def test_coding_consequence_classification():
    assert _coding_consequence(0, "M", "L") == "start_lost"
    assert _coding_consequence(5, "V", "*") == "stop_gained"
    assert _coding_consequence(5, "*", "R") == "stop_lost"
    assert _coding_consequence(5, "V", "V") == "synonymous"
    assert _coding_consequence(5, "V", "E") == "missense"


def _transcript(strand, cds):
    return {"strand": strand, "cds": cds}


def test_cds_offset_forward_strand():
    transcript = _transcript("+", [(100, 150), (200, 250)])
    assert _cds_offset(transcript, 100, "+") == 0
    assert _cds_offset(transcript, 101, "+") == 1
    assert _cds_offset(transcript, 200, "+") == 51
    assert _cds_offset(transcript, 205, "+") == 56
    assert _cds_offset(transcript, 175, "+") is None


def test_cds_offset_reverse_strand():
    transcript = _transcript("-", [(100, 150), (200, 250)])
    # On the reverse strand the transcript reads from the last segment backward.
    assert _cds_offset(transcript, 250, "-") == 0
    assert _cds_offset(transcript, 249, "-") == 1
    assert _cds_offset(transcript, 200, "-") == 50
    assert _cds_offset(transcript, 150, "-") == 51
    assert _cds_offset(transcript, 100, "-") == 101


def test_query_overlaps_finds_containing_segments():
    starts = np.array([100, 200, 900], dtype=np.int64)
    ends = np.array([150, 250, 950], dtype=np.int64)
    tidx = np.array([0, 1, 2], dtype=np.int64)
    max_end = np.maximum.accumulate(ends)
    index = {"7": (starts, ends, tidx, max_end)}

    assert sorted(_query_overlaps(index, "7", 120)) == [0]
    assert sorted(_query_overlaps(index, "7", 200)) == [1]
    assert sorted(_query_overlaps(index, "7", 300)) == []
    assert _query_overlaps(index, "1", 120) == []


def test_unavailable_without_data(monkeypatch):
    annotator = OfflineAnnotator(reference_build="GRCh38")
    monkeypatch.setattr("app.annotation.offline._gtf_path", lambda build: _missing())
    assert annotator.is_available() is False


def _missing():
    from pathlib import Path

    return Path("/nonexistent/does-not-exist.gtf.gz")


@pytest.mark.skipif(not _GRCH38_READY, reason="offline GRCh38 reference not downloaded")
def test_offline_annotates_braf_v600e(monkeypatch):
    monkeypatch.setattr(settings, "OFFLINE_REFERENCE_DIR", str(_REAL_REFERENCE))
    annotator = OfflineAnnotator(reference_build="GRCh38")
    assert annotator.is_available() is True
    [record] = annotator.annotate(
        [_variant("chr7", 140753336, "A", "T")],
        ReferenceContext(reference_build="GRCh38"),
    )
    assert record.gene == "BRAF"
    assert record.consequence == "missense"
    assert record.protein_change == "p.V600E"
    assert record.protein_position == 600
    assert record.mutated_peptide
    assert "E" in record.mutated_peptide


# ---- thread isolation (SQLite connections must not cross threads) -----------


def test_offline_index_connection_is_per_thread(tmp_path):
    import sqlite3
    import threading

    from app.annotation.offline import _OfflineIndex

    db = tmp_path / "cds.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE cds (tid TEXT PRIMARY KEY, seq TEXT NOT NULL)")
    con.execute("INSERT INTO cds VALUES ('ENST00000001', 'ATGAAA')")
    con.commit()
    con.close()

    index = _OfflineIndex(
        {
            "transcripts": [],
            "cds_index": {},
            "exon_index": {},
            "span_index": {},
            "release": "test",
            "genome_build": "GRCh38",
        },
        db,
    )

    out: dict[int, object] = {}
    errors: list[Exception] = []

    def worker(name: int) -> None:
        try:
            out[name] = (index._connection(), index.cds_sequence("ENST00000001"))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, errors
    assert out[0][1] == "ATGAAA" and out[1][1] == "ATGAAA"
    # Distinct connection per thread (never shared across threads).
    assert out[0][0] is not out[1][0]


@pytest.mark.skipif(not _GRCH38_READY, reason="offline GRCh38 reference not downloaded")
def test_offline_annotator_is_thread_safe(monkeypatch):
    """The process-wide cached index must be usable from worker threads.

    Regression: a single cached sqlite3 connection raised
    "SQLite objects created in a thread can only be used in that same thread"
    when annotation ran in a different thread (e.g. the one-click job pool).
    """
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setattr(settings, "OFFLINE_REFERENCE_DIR", str(_REAL_REFERENCE))

    def annotate(_index: int) -> tuple[str | None, str | None]:
        annotator = OfflineAnnotator(reference_build="GRCh38")
        [record] = annotator.annotate(
            [_variant("chr7", 140753336, "A", "T")],
            ReferenceContext(reference_build="GRCh38"),
        )
        return record.gene, record.protein_change

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(annotate, range(6)))

    assert all(result == ("BRAF", "p.V600E") for result in results), results
