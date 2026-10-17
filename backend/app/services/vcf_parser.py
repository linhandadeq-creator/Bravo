"""VCF parsing and raw structural validation.

Parsing is delegated to :mod:`pysam` (a mature htslib-backed VCF parser). Before
handing the file to pysam we run a raw structural scan so that *malformed*,
*missing-field* and *column-mismatch* records can be reported individually
instead of aborting the whole file. Records that pass the structural scan are
written to a cleaned temporary VCF and parsed by pysam, from which we extract
CHROM/POS/ID/REF/ALT/QUAL/FILTER/INFO/FORMAT plus DP, AD, AF and GT.
"""
from __future__ import annotations

import gzip
import os
import re
import tempfile
from dataclasses import dataclass, field

try:  # optional dependency: Windows has no pysam wheels, a pure-Python fallback is used
    import pysam  # type: ignore[import-not-found]
except Exception:  # noqa: BLE001
    pysam = None  # type: ignore[assignment]

from app.core.chromosomes import normalize_chromosome

_ALLELE_RE = re.compile(r"^[ACGTNacgtn]+$")
_SYMBOLIC_RE = re.compile(r"[<>\[\]]")


@dataclass
class ParsedVariant:
    line_number: int
    chromosome: str | None
    chromosome_normalized: str | None
    chromosome_changed: bool
    chromosome_known: bool
    position: int | None
    reference: str | None
    alternate: str | None
    quality: float | None
    filter: str | None
    depth: int | None
    allele_frequency: float | None
    genotype: str | None
    variant_type: str | None
    record_id: str | None
    info: dict | None
    format_fields: dict | None
    is_valid: bool
    is_duplicate: bool
    is_malformed: bool
    invalid_reason: str | None = None

    @property
    def key(self) -> tuple[str, int, str, str] | None:
        if self.position is None or not self.reference or not self.alternate:
            return None
        chrom = self.chromosome_normalized or self.chromosome or ""
        return (chrom, self.position, self.reference.upper(), self.alternate.upper())


@dataclass
class ParseResult:
    role: str
    records: list[ParsedVariant] = field(default_factory=list)
    file_ok: bool = True
    format_ok: bool = True
    file_size_bytes: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def raw_count(self) -> int:
        return len(self.records)

    @property
    def malformed_count(self) -> int:
        return sum(1 for r in self.records if r.is_malformed)

    @property
    def invalid_count(self) -> int:
        return sum(1 for r in self.records if not r.is_valid)

    @property
    def valid_count(self) -> int:
        return sum(1 for r in self.records if r.is_valid)

    @property
    def duplicate_count(self) -> int:
        return sum(1 for r in self.records if r.is_valid and r.is_duplicate)

    @property
    def unique_count(self) -> int:
        return sum(1 for r in self.records if r.is_valid and not r.is_duplicate)

    @property
    def normalization_count(self) -> int:
        return sum(1 for r in self.records if r.chromosome_changed)

    @property
    def missing_field_count(self) -> int:
        return sum(
            1
            for r in self.records
            if r.invalid_reason and "missing" in r.invalid_reason
        )

    def unique_valid_variants(self) -> list[ParsedVariant]:
        return [r for r in self.records if r.is_valid and not r.is_duplicate]


def _to_jsonable(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _prepare_text(path: str) -> tuple[str, str | None]:
    """Return a path to a plain-text VCF, decompressing ``.gz`` when needed."""
    if not path.endswith(".gz"):
        return path, None
    fd, tmp = tempfile.mkstemp(suffix=".vcf")
    os.close(fd)
    with gzip.open(path, "rt") as src, open(tmp, "w") as dst:
        for line in src:
            dst.write(line)
    return tmp, tmp


def _structural_error(cols: list[str], expected_ncols: int | None) -> str | None:
    if len(cols) < 8:
        return f"malformed record: expected at least 8 columns, found {len(cols)}"
    if expected_ncols is not None and len(cols) != expected_ncols:
        return (
            f"malformed record: expected {expected_ncols} columns "
            f"to match header, found {len(cols)}"
        )
    if not cols[0].strip():
        return "missing CHROM"
    pos = cols[1].strip()
    if not pos.isdigit() or int(pos) <= 0:
        return f"malformed record: invalid POS '{cols[1]}'"
    if not cols[3].strip():
        return "missing REF"
    if not cols[4].strip() or cols[4].strip() == ".":
        return "missing ALT"
    return None


def _allele_issue(reference: str, alternate: str | None, alt_count: int) -> str | None:
    if alt_count > 1:
        return "multiallelic records are not supported"
    if alternate is None or alternate in ("", "."):
        return "missing ALT"
    if alternate == reference:
        return "invalid allele: REF equals ALT"
    if _SYMBOLIC_RE.search(alternate) or alternate == "*":
        return "invalid allele: unsupported symbolic/structural allele"
    if not _ALLELE_RE.match(reference):
        return "invalid allele: REF contains non-ACGTN characters"
    if not _ALLELE_RE.match(alternate):
        return "invalid allele: ALT contains non-ACGTN characters"
    return None


def _variant_type(reference: str, alternate: str | None) -> str:
    if alternate is None:
        return "UNKNOWN"
    if _SYMBOLIC_RE.search(alternate) or alternate == "*":
        return "SYMBOLIC"
    if len(reference) == 1 and len(alternate) == 1:
        return "SNV"
    if len(reference) == 1 and len(alternate) > 1:
        return "INSERTION"
    if len(reference) > 1 and len(alternate) == 1:
        return "DELETION"
    if len(reference) > 1 and len(alternate) > 1 and len(reference) == len(alternate):
        return "MNV"
    return "INDEL"


def _as_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _sample_get(sample, key: str):
    try:
        if key in sample.keys():
            return sample[key]
    except Exception:  # noqa: BLE001 - defensive; missing FORMAT field
        return None
    return None


def _extract_record(record, line_number: int) -> ParsedVariant:
    reference = record.ref
    alts = list(record.alts or [])
    alternate = alts[0] if alts else None

    info: dict = {}
    for key in record.info.keys():
        try:
            info[key] = _to_jsonable(record.info[key])
        except Exception:  # noqa: BLE001 - defensive; malformed INFO values
            info[key] = None

    genotype = None
    format_fields: dict | None = None
    depth = None
    allele_frequency = None
    ad = None
    if record.samples:
        sample = next(iter(record.samples.values()))
        format_fields = {}
        for key in sample.keys():
            format_fields[key] = _to_jsonable(sample[key])

        gt_value = _sample_get(sample, "GT")
        if gt_value is not None:
            sep = "|" if getattr(sample, "phased", False) else "/"
            genotype = sep.join("." if a is None else str(a) for a in gt_value)

        ad = _sample_get(sample, "AD")
        depth = _as_int(_sample_get(sample, "DP"))
        allele_frequency = _as_float(_sample_get(sample, "AF"))

    if depth is None:
        depth = _as_int(info.get("DP"))
    if allele_frequency is None:
        allele_frequency = _as_float(info.get("AF"))
    if allele_frequency is None and ad and len(ad) >= 2:
        total = sum(int(x) for x in ad if x is not None)
        if total > 0:
            allele_frequency = int(ad[1]) / total
    if depth is None and ad:
        depth = sum(int(x) for x in ad if x is not None)

    chrom_norm = normalize_chromosome(record.chrom)
    reason = _allele_issue(reference, alternate, len(alts))
    if reason is None and not chrom_norm.known:
        reason = f"unknown chromosome '{record.chrom}'"

    return ParsedVariant(
        line_number=line_number,
        chromosome=record.chrom,
        chromosome_normalized=chrom_norm.normalized or None,
        chromosome_changed=chrom_norm.changed,
        chromosome_known=chrom_norm.known,
        position=record.pos,
        reference=reference,
        alternate=alternate,
        quality=record.qual,
        filter=";".join(list(record.filter)) if record.filter else None,
        depth=depth,
        allele_frequency=allele_frequency,
        genotype=genotype,
        variant_type=_variant_type(reference, alternate),
        record_id=record.id,
        info=info,
        format_fields=format_fields,
        is_valid=reason is None,
        is_duplicate=False,
        is_malformed=False,
        invalid_reason=reason,
    )


def _parse_info(raw: str) -> dict:
    info: dict = {}
    if not raw or raw == ".":
        return info
    for entry in raw.split(";"):
        if not entry:
            continue
        if "=" in entry:
            key, value = entry.split("=", 1)
            parts = value.split(",")
            info[key] = parts if len(parts) > 1 else parts[0]
        else:
            info[entry] = True
    return info


class _TextSample(dict):
    """Minimal stand-in for a pysam sample mapping."""

    phased = False


def _parse_sample(keys: list[str], raw: str) -> _TextSample:
    sample = _TextSample()
    values = raw.split(":")
    for index, key in enumerate(keys):
        value = values[index] if index < len(values) else None
        if value in (None, "", "."):
            sample[key] = None
            continue
        if key == "GT":
            sample.phased = "|" in value
            sample[key] = tuple(
                None if allele == "." else int(allele)
                for allele in value.replace("|", "/").split("/")
            )
        elif key == "AD":
            sample[key] = [int(part) if part.isdigit() else None for part in value.split(",")]
        elif key == "DP":
            sample[key] = _as_int(value)
        elif key == "AF":
            sample[key] = _as_float(value)
        else:
            parts = value.split(",")
            sample[key] = parts if len(parts) > 1 else parts[0]
    return sample


class _TextRecord:
    """Minimal stand-in for a pysam VariantRecord (used when pysam is absent)."""

    def __init__(
        self,
        *,
        chrom: str,
        pos: int,
        record_id: str | None,
        ref: str,
        alts: list[str] | None,
        qual: float | None,
        filters: list[str],
        info: dict,
        samples: dict,
    ) -> None:
        self.chrom = chrom
        self.pos = pos
        self.id = record_id
        self.ref = ref
        self.alts = alts
        self.qual = qual
        self.filter = filters
        self.info = info
        self.samples = samples


def _read_text_records(path: str) -> list[_TextRecord]:
    records: list[_TextRecord] = []
    sample_names: list[str] = []
    with open(path, "r", errors="replace") as handle:
        for line in handle:
            line = line.rstrip("\r\n")
            if line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                cols = line.split("\t")
                if len(cols) > 9 and cols[8] == "FORMAT":
                    sample_names = cols[9:]
                continue
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 8:
                continue
            chrom, pos, record_id, ref, alt, qual, filt, info_raw = cols[:8]
            format_raw = cols[8] if len(cols) > 8 else ""
            sample_cols = cols[9:] if len(cols) > 9 else []
            info = _parse_info(info_raw)
            alts = None if alt in ("", ".") else alt.split(",")
            samples: dict = {}
            if format_raw and sample_names:
                keys = format_raw.split(":")
                for name, raw in zip(sample_names, sample_cols):
                    samples[name] = _parse_sample(keys, raw)
            try:
                position = int(pos)
            except ValueError:
                continue
            records.append(
                _TextRecord(
                    chrom=chrom,
                    pos=position,
                    record_id=None if record_id in ("", ".") else record_id,
                    ref=ref,
                    alts=alts,
                    qual=_as_float(qual),
                    filters=[] if filt in ("", ".") else filt.split(";"),
                    info=info,
                    samples=samples,
                )
            )
    return records


def _read_records(path: str) -> list:
    if pysam is not None:
        with pysam.VariantFile(path) as vcf:
            return list(vcf)
    return _read_text_records(path)


def parse_vcf(path: str, role: str = "TUMOR") -> ParseResult:
    result = ParseResult(role=role)

    if not os.path.isfile(path):
        result.file_ok = False
        result.errors.append(f"{role} VCF file not found: {path}")
        return result

    result.file_size_bytes = os.path.getsize(path)
    if result.file_size_bytes == 0:
        result.file_ok = False
        result.errors.append(f"{role} VCF file is empty")
        return result

    text_path: str | None = None
    cleanup: str | None = None
    try:
        text_path, cleanup = _prepare_text(path)
    except Exception as exc:  # noqa: BLE001 - corrupt gzip / unreadable file
        result.file_ok = False
        result.errors.append(f"{role} VCF could not be read: {exc}")
        return result

    try:
        with open(text_path, "r", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError as exc:
        result.file_ok = False
        result.errors.append(f"{role} VCF could not be read: {exc}")
        return result
    finally:
        if cleanup and os.path.exists(cleanup):
            os.remove(cleanup)

    header_lines: list[str] = []
    chrom_header: str | None = None
    data_lines: list[tuple[int, str]] = []
    for number, line in enumerate(lines, start=1):
        if line.startswith("#"):
            header_lines.append(line)
            if line.startswith("#CHROM"):
                chrom_header = line
            continue
        if not line.strip():
            continue
        data_lines.append((number, line))

    if chrom_header is None:
        result.format_ok = False
        result.errors.append(
            f"{role} VCF is missing the #CHROM header line; not a valid VCF"
        )

    expected_ncols = len(chrom_header.split("\t")) if chrom_header else None

    accepted: list[tuple[int, list[str]]] = []
    for number, line in data_lines:
        cols = line.split("\t")
        reason = _structural_error(cols, expected_ncols)
        if reason is not None:
            result.records.append(
                ParsedVariant(
                    line_number=number,
                    chromosome=cols[0] or None,
                    chromosome_normalized=None,
                    chromosome_changed=False,
                    chromosome_known=False,
                    position=None,
                    reference=cols[3] if len(cols) > 3 else None,
                    alternate=cols[4] if len(cols) > 4 else None,
                    quality=None,
                    filter=None,
                    depth=None,
                    allele_frequency=None,
                    genotype=None,
                    variant_type=None,
                    record_id=None,
                    info=None,
                    format_fields=None,
                    is_valid=False,
                    is_duplicate=False,
                    is_malformed=True,
                    invalid_reason=reason,
                )
            )
            continue
        accepted.append((number, cols))

    if not accepted:
        if not result.records:
            result.warnings.append(f"{role} VCF contains no variant records")
        _mark_duplicates(result)
        return result

    fd, clean_path = tempfile.mkstemp(suffix=".vcf")
    os.close(fd)
    try:
        with open(clean_path, "w") as handle:
            if chrom_header is not None:
                handle.write("\n".join(header_lines) + "\n")
            else:
                handle.write("##fileformat=VCFv4.2\n")
                handle.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
            for _, cols in accepted:
                handle.write("\t".join(cols) + "\n")

        try:
            records = _read_records(clean_path)
        except Exception as exc:  # noqa: BLE001 - parser could not read the file
            result.format_ok = False
            result.errors.append(f"{role} VCF could not be parsed: {exc}")
            _mark_duplicates(result)
            return result

        if len(records) != len(accepted):
            result.warnings.append(
                f"{role} VCF: parsed {len(records)} of {len(accepted)} records"
            )

        for (number, _cols), record in zip(accepted, records):
            result.records.append(_extract_record(record, number))
    finally:
        if os.path.exists(clean_path):
            os.remove(clean_path)

    _mark_duplicates(result)
    return result


def _mark_duplicates(result: ParseResult) -> None:
    seen: set[tuple[str, int, str, str]] = set()
    for variant in result.records:
        if not variant.is_valid:
            continue
        key = variant.key
        if key is None:
            continue
        if key in seen:
            variant.is_duplicate = True
        else:
            seen.add(key)
