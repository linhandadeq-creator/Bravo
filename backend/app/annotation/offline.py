"""Fully-offline annotator — real annotation with no external service.

Uses a local Ensembl release (GTF transcript structure + CDS FASTA) to compute,
for each variant, the real gene, transcript, coding consequence, protein change
and the mutant peptide context. Nothing is fetched from the network at runtime,
so annotation works even when the Ensembl REST service is down.

Data layout (per build), under ``settings.offline_reference_path``::

    GRCh38/Homo_sapiens.GRCh38.112.gtf.gz
    GRCh38/Homo_sapiens.GRCh38.cds.all.fa.gz

On first use the sources are compiled into a pickled interval index
(``annotation_index.pkl``) plus a CDS sequence store (``cds.sqlite``). If the
data is absent the provider reports itself as UNAVAILABLE — it never falls back
to the mock annotator.
"""
from __future__ import annotations

import gzip
import pickle
import sqlite3
import threading
from pathlib import Path

import numpy as np

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
from app.annotation.vep import _CODON_TABLE, _build_peptide, _translate
from app.core.config import settings
from app.core.reference import GRCH37, GRCH38

_BUILD_RELEASE = {GRCH38: "112", GRCH37: "87"}

_COMPLEMENT = str.maketrans("ACGTN", "TGCAN")

_IMPACT = {
    Consequence.MISSENSE.value: Impact.MODERATE.value,
    Consequence.FRAMESHIFT.value: Impact.HIGH.value,
    Consequence.STOP_GAINED.value: Impact.HIGH.value,
    Consequence.STOP_LOST.value: Impact.HIGH.value,
    Consequence.START_LOST.value: Impact.HIGH.value,
    Consequence.SPLICE_RELATED.value: Impact.HIGH.value,
    Consequence.INFRAME_INSERTION.value: Impact.MODERATE.value,
    Consequence.INFRAME_DELETION.value: Impact.MODERATE.value,
    Consequence.SYNONYMOUS.value: Impact.LOW.value,
    Consequence.UNKNOWN.value: Impact.MODIFIER.value,
}

_lock = threading.Lock()
_loaded: dict[str, "_OfflineIndex"] = {}
_clinvar_cache: dict[str, dict[tuple, dict]] = {}


def _clinvar_path(build: str) -> Path:
    explicit = (getattr(settings, "CLINVAR_VCF", "") or "").strip()
    if explicit and Path(explicit).is_file():
        return Path(explicit)
    by_settings = settings.offline_reference_path / build / "homo_sapiens_clinically_associated.vcf.gz"
    if by_settings.is_file():
        return by_settings
    repo = (
        Path(__file__).resolve().parents[2]
        / "storage"
        / "reference"
        / build
        / "homo_sapiens_clinically_associated.vcf.gz"
    )
    return repo


def _load_clinvar(build: str) -> dict[tuple, dict]:
    if build in _clinvar_cache:
        return _clinvar_cache[build]
    table: dict[tuple, dict] = {}
    path = _clinvar_path(build)
    if path.is_file():
        opener = gzip.open if str(path).endswith(".gz") else open
        with opener(path, "rt") as handle:
            for line in handle:
                if line.startswith("#"):
                    continue
                fields = line.rstrip("\n").split("\t")
                if len(fields) < 8:
                    continue
                chrom = fields[0].replace("chr", "")
                try:
                    pos = int(fields[1])
                except ValueError:
                    continue
                variant_id = fields[2]
                ref = fields[3].upper()
                info = fields[7]
                clin: list[str] = []
                for token in info.split(";"):
                    if token.startswith("CLIN_"):
                        clin.append(token[5:].replace("_", " ").strip())
                clin_sig = "; ".join(dict.fromkeys(clin)) or None
                for alt in fields[4].upper().split(","):
                    if alt in (".", "*", ""):
                        continue
                    table[(chrom, pos, ref, alt)] = {
                        "id": None if variant_id == "." else variant_id,
                        "clin": clin_sig,
                    }
    _clinvar_cache[build] = table
    return table


def clinvar_status(build: str = GRCH38) -> dict:
    path = _clinvar_path(build)
    available = path.is_file()
    return {
        "available": available,
        "source": str(path) if available else None,
        "entries": len(_load_clinvar(build)) if available else 0,
    }


def _clinvar_lookup(
    build: str, chromosome: str | None, position: int | None, ref: str | None, alt: str | None
) -> dict | None:
    if not chromosome or not position:
        return None
    return _load_clinvar(build).get(
        (chromosome.replace("chr", ""), int(position), (ref or "").upper(), (alt or "").upper())
    )


def _build_dir(build: str) -> Path:
    return settings.offline_reference_path / build


def _gtf_path(build: str) -> Path:
    return _build_dir(build) / f"Homo_sapiens.{build}.{_BUILD_RELEASE.get(build, '')}.gtf.gz"


def _cds_fasta_path(build: str) -> Path:
    return _build_dir(build) / f"Homo_sapiens.{build}.cds.all.fa.gz"


def _index_path(build: str) -> Path:
    return _build_dir(build) / "annotation_index.pkl"


def _cds_db_path(build: str) -> Path:
    return _build_dir(build) / "cds.sqlite"


def _parse_attributes(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for field in raw.strip().strip(";").split(";"):
        field = field.strip()
        if not field or " " not in field:
            continue
        key, _, value = field.partition(" ")
        attrs[key.strip()] = value.strip().strip('"')
    return attrs


class _OfflineIndex:
    def __init__(self, payload: dict, cds_db: Path) -> None:
        self.transcripts: list[dict] = payload["transcripts"]
        self.cds_index: dict[str, tuple] = payload["cds_index"]
        self.exon_index: dict[str, tuple] = payload["exon_index"]
        self.span_index: dict[str, tuple] = payload["span_index"]
        self.release: str = payload["release"]
        self.genome_build: str = payload["genome_build"]
        self.cds_db = cds_db
        # A single sqlite3 connection must not cross threads. The index is
        # cached process-wide, so each thread gets its own read-only
        # connection via thread-local storage (``check_same_thread`` stays at
        # its safe default of True).
        self._local = threading.local()
        self._protein_lock = threading.Lock()
        self._protein_cache: dict[int, str] = {}

    def _connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                f"file:{self.cds_db}?mode=ro", uri=True, check_same_thread=True
            )
            self._local.conn = conn
        return conn

    def cds_sequence(self, tid: str) -> str | None:
        row = self._connection().execute(
            "SELECT seq FROM cds WHERE tid = ?", (tid,)
        ).fetchone()
        return row[0] if row else None

    def protein(self, tidx: int) -> str | None:
        with self._protein_lock:
            cached = self._protein_cache.get(tidx)
        if cached is not None:
            return cached or None
        cds = self.cds_sequence(self.transcripts[tidx]["tid"])
        protein = _translate(cds) if cds else ""
        with self._protein_lock:
            self._protein_cache[tidx] = protein
        return protein or None


def _query_overlaps(index: dict[str, tuple], chrom: str, pos: int) -> list[int]:
    entry = index.get(chrom)
    if entry is None:
        return []
    starts, ends, tidx, max_end = entry
    i = int(np.searchsorted(starts, pos, side="right")) - 1
    hits: list[int] = []
    while i >= 0 and max_end[i] >= pos:
        if ends[i] >= pos:
            hits.append(int(tidx[i]))
        i -= 1
    return hits


def _build_index(build: str) -> dict:
    gtf = _gtf_path(build)
    cds_fa = _cds_fasta_path(build)
    if not gtf.exists() or not cds_fa.exists():
        raise FileNotFoundError(
            f"Offline reference for {build} is missing ({gtf.name} / {cds_fa.name})."
        )

    transcripts: dict[str, dict] = {}
    cds_segments: list[tuple[str, int, int, str]] = []
    exon_segments: list[tuple[str, int, int, str]] = []
    release = _BUILD_RELEASE.get(build, "unknown")
    genome_build = build

    with gzip.open(gtf, "rt") as handle:
        for line in handle:
            if line.startswith("#"):
                if line.startswith("#!") and "genome-build" in line:
                    parts = line[1:].strip().split()
                    if len(parts) >= 4:
                        genome_build = parts[1]
                        release = parts[3]
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 9:
                continue
            chrom, _, feature, start, end, _, strand, _, attr_raw = fields[:9]
            if feature not in ("transcript", "CDS", "exon"):
                continue
            attrs = _parse_attributes(attr_raw)
            tid = attrs.get("transcript_id")
            if not tid:
                continue
            if feature == "transcript":
                tags = set()
                raw_attr = attr_raw
                for token in raw_attr.split(";"):
                    token = token.strip()
                    if token.startswith("tag "):
                        tags.add(token[4:].strip().strip('"'))
                transcripts[tid] = {
                    "tid": tid,
                    "gene_id": attrs.get("gene_id"),
                    "gene": attrs.get("gene_name") or attrs.get("gene_id"),
                    "chrom": chrom.replace("chr", ""),
                    "strand": strand,
                    "biotype": attrs.get("transcript_biotype")
                    or attrs.get("biotype"),
                    "canonical": "Ensembl_canonical" in tags,
                    "mane": "MANE_Select" in tags,
                }
            elif feature == "CDS":
                cds_segments.append((chrom.replace("chr", ""), int(start), int(end), tid))
            elif feature == "exon":
                exon_segments.append((chrom.replace("chr", ""), int(start), int(end), tid))

    order = {tid: i for i, tid in enumerate(transcripts)}
    cds_lists: dict[int, list[tuple[int, int]]] = {}
    exon_lists: dict[int, list[tuple[int, int]]] = {}
    for chrom, start, end, tid in cds_segments:
        idx = order.get(tid)
        if idx is not None:
            cds_lists.setdefault(idx, []).append((start, end))
    for chrom, start, end, tid in exon_segments:
        idx = order.get(tid)
        if idx is not None:
            exon_lists.setdefault(idx, []).append((start, end))

    for idx, transcript in enumerate(transcripts.values()):
        transcript["cds"] = sorted(cds_lists.get(idx, []))

    def _build_interval_index(
        segments: list[tuple[str, int, int, str]]
    ) -> dict[str, tuple]:
        grouped: dict[str, list[tuple[int, int, int]]] = {}
        for chrom, start, end, tid in segments:
            idx = order.get(tid)
            if idx is None:
                continue
            grouped.setdefault(chrom, []).append((start, end, idx))
        result: dict[str, tuple] = {}
        for chrom, items in grouped.items():
            items.sort(key=lambda item: item[0])
            starts = np.array([item[0] for item in items], dtype=np.int64)
            ends = np.array([item[1] for item in items], dtype=np.int64)
            tidx = np.array([item[2] for item in items], dtype=np.int64)
            max_end = np.maximum.accumulate(ends)
            result[chrom] = (starts, ends, tidx, max_end)
        return result

    cds_index = _build_interval_index(cds_segments)
    exon_index = _build_interval_index(exon_segments)

    span_segments: list[tuple[str, int, int, str]] = []
    for transcript in transcripts.values():
        exons = exon_lists.get(order[transcript["tid"]])
        if exons:
            span_segments.append(
                (
                    transcript["chrom"],
                    min(item[0] for item in exons),
                    max(item[1] for item in exons),
                    transcript["tid"],
                )
            )
    span_index = _build_interval_index(span_segments)

    _write_cds_db(cds_fa, _cds_db_path(build))

    payload = {
        "transcripts": list(transcripts.values()),
        "cds_index": cds_index,
        "exon_index": exon_index,
        "span_index": span_index,
        "release": release,
        "genome_build": genome_build,
    }
    with open(_index_path(build), "wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return payload


def _write_cds_db(cds_fa: Path, destination: Path) -> None:
    if destination.exists():
        destination.unlink()
    conn = sqlite3.connect(destination)
    conn.execute("CREATE TABLE cds (tid TEXT PRIMARY KEY, seq TEXT NOT NULL)")
    batch: list[tuple[str, str]] = []
    tid: str | None = None
    chunks: list[str] = []

    def _flush() -> None:
        nonlocal tid, chunks
        if tid is not None and chunks:
            seq = "".join(chunks).replace("\n", "").upper()
            batch.append((tid, seq))
        tid, chunks = None, []

    with gzip.open(cds_fa, "rt") as handle:
        for line in handle:
            if line.startswith(">"):
                _flush()
                header = line[1:].strip()
                token = header.split()[0]
                tid = token.split(".")[0]
            else:
                chunks.append(line.strip())
        _flush()
        if batch:
            conn.executemany("INSERT OR REPLACE INTO cds (tid, seq) VALUES (?, ?)", batch)
            batch.clear()
    conn.commit()
    conn.execute("CREATE INDEX idx_cds_tid ON cds (tid)")
    conn.commit()
    conn.close()


def _load_index(build: str) -> _OfflineIndex:
    if build in _loaded:
        return _loaded[build]
    with _lock:
        if build in _loaded:
            return _loaded[build]
        index_file = _index_path(build)
        gtf = _gtf_path(build)
        cds_db = _cds_db_path(build)
        stale = (
            not index_file.exists()
            or not cds_db.exists()
            or (gtf.exists() and index_file.stat().st_mtime < gtf.stat().st_mtime)
        )
        if stale:
            payload = _build_index(build)
        else:
            with open(index_file, "rb") as handle:
                payload = pickle.load(handle)
        _loaded[build] = _OfflineIndex(payload, cds_db)
        return _loaded[build]


def _cds_offset(transcript: dict, pos: int, strand: str) -> int | None:
    segments = transcript["cds"]
    if not segments:
        return None
    ordered = segments if strand != "-" else list(reversed(segments))
    offset = 0
    for start, end in ordered:
        if start <= pos <= end:
            if strand == "-":
                return offset + (end - pos)
            return offset + (pos - start)
        offset += end - start + 1
    return None


def _select_transcript(index: _OfflineIndex, tidxs: list[int]) -> int | None:
    if not tidxs:
        return None
    protein_coding = [
        t for t in tidxs if index.transcripts[t]["biotype"] == "protein_coding"
    ]
    pool = protein_coding or tidxs
    mane = [t for t in pool if index.transcripts[t]["mane"]]
    if mane:
        pool = mane
    canonical = [t for t in pool if index.transcripts[t]["canonical"]]
    if canonical:
        pool = canonical
    return max(pool, key=lambda t: sum(e - s + 1 for s, e in index.transcripts[t]["cds"]))


def _codon_aa(codon: str) -> str:
    return _CODON_TABLE.get(codon.upper(), "X")


def _coding_consequence(codon_index: int, ref_aa: str, alt_aa: str) -> str:
    if codon_index == 0 and ref_aa == "M" and alt_aa != "M":
        return Consequence.START_LOST.value
    if alt_aa == "*":
        return Consequence.STOP_GAINED.value
    if ref_aa == "*" and alt_aa != "*":
        return Consequence.STOP_LOST.value
    if ref_aa == alt_aa:
        return Consequence.SYNONYMOUS.value
    return Consequence.MISSENSE.value


@register
class OfflineAnnotator(VariantAnnotator):
    name = "offline"

    def metadata(self) -> ProviderMetadata:
        build = self.reference_build or GRCH38
        release = _BUILD_RELEASE.get(build, "unknown")
        return ProviderMetadata(
            provider=self.name,
            provider_version=f"Ensembl {release} (offline)",
            reference_build=build,
            annotation_version=f"Ensembl release {release}",
            transcript_source="Ensembl",
            description=(
                "Fully-offline annotation from a local Ensembl GTF + CDS FASTA "
                "(no network required)."
            ),
        )

    def is_available(self) -> bool:
        build = self.reference_build or GRCH38
        return _gtf_path(build).exists() and _cds_fasta_path(build).exists()

    def annotate(
        self, variants: list[VariantInput], reference_context: ReferenceContext
    ) -> list[AnnotationRecord]:
        build = reference_context.reference_build or self.reference_build or GRCH38
        index = _load_index(build)
        records: list[AnnotationRecord] = []
        for variant in variants:
            record = self._annotate_one(index, variant)
            clinvar = _clinvar_lookup(
                build, variant.chromosome, variant.position, variant.reference, variant.alternate
            )
            if clinvar:
                extra = dict(record.extra or {})
                if clinvar.get("id"):
                    known = list(extra.get("known_variants") or [])
                    known.append(clinvar["id"])
                    extra["known_variants"] = known
                if clinvar.get("clin"):
                    extra["clinical_significance"] = clinvar["clin"]
                record.extra = extra
            records.append(record)
        return records

    def _annotate_one(self, index: _OfflineIndex, variant: VariantInput) -> AnnotationRecord:
        chrom = (variant.chromosome or "").replace("chr", "")
        pos = variant.position
        ref = (variant.reference or "").upper()
        alt = (variant.alternate or "").upper()
        if not chrom or not pos or not ref or not alt:
            return self._unknown(variant)

        cds_tidxs = _query_overlaps(index.cds_index, chrom, pos)
        tidx = _select_transcript(index, cds_tidxs)
        if tidx is not None:
            return self._annotate_coding(index, variant, tidx, pos, ref, alt)

        exon_tidxs = _query_overlaps(index.exon_index, chrom, pos)
        if exon_tidxs:
            tidx = _select_transcript(index, exon_tidxs)
            transcript = index.transcripts[tidx]
            return AnnotationRecord(
                key=variant.key,
                status=AnnotationStatus.ANNOTATED.value,
                consequence=Consequence.UNKNOWN.value,
                impact=Impact.MODIFIER.value,
                gene=transcript["gene"],
                gene_id=transcript["gene_id"],
                transcript=transcript["tid"],
                transcript_id=transcript["tid"],
            )

        span_tidxs = _query_overlaps(index.span_index, chrom, pos)
        if span_tidxs:
            tidx = _select_transcript(index, span_tidxs)
            transcript = index.transcripts[tidx]
            return AnnotationRecord(
                key=variant.key,
                status=AnnotationStatus.PARTIAL.value,
                consequence=Consequence.SPLICE_RELATED.value,
                impact=Impact.HIGH.value,
                gene=transcript["gene"],
                gene_id=transcript["gene_id"],
                transcript=transcript["tid"],
                transcript_id=transcript["tid"],
            )

        return self._unknown(variant)

    def _annotate_coding(
        self,
        index: _OfflineIndex,
        variant: VariantInput,
        tidx: int,
        pos: int,
        ref: str,
        alt: str,
    ) -> AnnotationRecord:
        transcript = index.transcripts[tidx]
        strand = transcript["strand"]
        tid = transcript["tid"]
        offset = _cds_offset(transcript, pos, strand)
        base = dict(
            key=variant.key,
            gene=transcript["gene"],
            gene_id=transcript["gene_id"],
            transcript=tid,
            transcript_id=tid,
        )

        length_delta = len(alt) - len(ref)
        if len(ref) != 1 or len(alt) != 1:
            if length_delta == 0:
                consequence = Consequence.MISSENSE.value
            elif length_delta % 3 == 0:
                consequence = (
                    Consequence.INFRAME_INSERTION.value
                    if length_delta > 0
                    else Consequence.INFRAME_DELETION.value
                )
            else:
                consequence = Consequence.FRAMESHIFT.value
            return AnnotationRecord(
                **base,
                status=AnnotationStatus.PARTIAL.value,
                consequence=consequence,
                impact=_IMPACT[consequence],
                cds_position=(offset + 1) if offset is not None else None,
            )

        if offset is None:
            return AnnotationRecord(
                **base,
                status=AnnotationStatus.PARTIAL.value,
                consequence=Consequence.SPLICE_RELATED.value,
                impact=Impact.HIGH.value,
            )

        cds = index.cds_sequence(tid)
        if not cds or offset >= len(cds):
            return AnnotationRecord(
                **base,
                status=AnnotationStatus.PARTIAL.value,
                consequence=Consequence.UNKNOWN.value,
                impact=Impact.MODIFIER.value,
            )

        coding_ref = ref if strand != "-" else ref.translate(_COMPLEMENT)
        coding_alt = alt if strand != "-" else alt.translate(_COMPLEMENT)
        if cds[offset] != coding_ref:
            # Reference mismatch — do not emit a possibly-wrong protein change.
            return AnnotationRecord(
                **base,
                status=AnnotationStatus.PARTIAL.value,
                consequence=Consequence.UNKNOWN.value,
                impact=Impact.MODIFIER.value,
                cds_position=offset + 1,
            )

        codon_index = offset // 3
        codon_pos = offset % 3
        ref_codon = list(cds[codon_index * 3 : codon_index * 3 + 3])
        if len(ref_codon) < 3:
            return AnnotationRecord(
                **base,
                status=AnnotationStatus.PARTIAL.value,
                consequence=Consequence.UNKNOWN.value,
                impact=Impact.MODIFIER.value,
            )
        alt_codon = ref_codon.copy()
        alt_codon[codon_pos] = coding_alt
        ref_aa = _codon_aa("".join(ref_codon))
        alt_aa = _codon_aa("".join(alt_codon))
        if ref_aa == "X" or alt_aa == "X":
            return AnnotationRecord(
                **base,
                status=AnnotationStatus.PARTIAL.value,
                consequence=Consequence.UNKNOWN.value,
                impact=Impact.MODIFIER.value,
            )

        consequence = _coding_consequence(codon_index, ref_aa, alt_aa)
        protein_position = codon_index + 1
        protein_change = (
            f"p.{ref_aa}{protein_position}*"
            if alt_aa == "*"
            else f"p.{ref_aa}{protein_position}{alt_aa}"
        )

        mutated_peptide = None
        if consequence in (
            Consequence.MISSENSE.value,
            Consequence.SYNONYMOUS.value,
            Consequence.STOP_LOST.value,
        ):
            protein = index.protein(tidx)
            mutated_peptide = _build_peptide(protein, protein_position, ref_aa, alt_aa)

        return AnnotationRecord(
            **base,
            status=AnnotationStatus.ANNOTATED.value,
            consequence=consequence,
            impact=_IMPACT[consequence],
            protein_change=protein_change,
            cds_position=offset + 1,
            protein_position=protein_position,
            mutated_peptide=mutated_peptide,
            extra={"source": "offline", "release": index.release},
        )

    @staticmethod
    def _unknown(variant: VariantInput) -> AnnotationRecord:
        return AnnotationRecord(
            key=variant.key,
            status=AnnotationStatus.ANNOTATED.value,
            consequence=Consequence.UNKNOWN.value,
            impact=Impact.MODIFIER.value,
        )
