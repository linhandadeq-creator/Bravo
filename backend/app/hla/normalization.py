"""Unified HLA normalization layer.

Normalizes alleles to the canonical ``HLA-<LOCUS>*<field>:<field>`` form,
derives the locus class (I/II) and reports format errors, unknown loci and
class mismatches. Invalid alleles never reach the prediction pipeline.
"""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass

NORMALIZATION_METHOD = "hla-allele-normalizer-v1"
NORMALIZATION_VERSION = "1.0.0"

CLASS_I_LOCI = {"A", "B", "C", "E", "F", "G"}
CLASS_II_LOCI = {
    "DRA",
    "DRB1",
    "DRB3",
    "DRB4",
    "DRB5",
    "DQA1",
    "DQB1",
    "DPA1",
    "DPB1",
    "DMA",
    "DMB",
    "DOA",
    "DOB",
}

_LETTERS_DIGITS = re.compile(r"^([A-Z]+)([0-9].*)$")


@dataclass
class HlaNormalization:
    raw: str
    normalized: str | None
    locus: str | None
    allele_class: str | None
    valid: bool
    reason: str | None = None


def locus_class(locus: str) -> str | None:
    if locus in CLASS_I_LOCI:
        return "I"
    if locus in CLASS_II_LOCI:
        return "II"
    return None


def _canonical_class(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip().upper()
    if candidate in ("I", "1", "CLASS I", "CLASS_I"):
        return "I"
    if candidate in ("II", "2", "CLASS II", "CLASS_II"):
        return "II"
    return candidate


def _invalid(raw: str, reason: str) -> HlaNormalization:
    return HlaNormalization(raw=raw, normalized=None, locus=None, allele_class=None, valid=False, reason=reason)


def normalize_hla_allele(
    raw: str | None, declared_class: str | None = None
) -> HlaNormalization:
    original = raw or ""
    value = original.strip().upper().replace(" ", "").replace("_", "-")
    if not value:
        return _invalid(original, "empty allele")

    if value.startswith("HLA-"):
        value = value[4:]

    if "*" in value:
        locus_part, rest = value.split("*", 1)
    else:
        match = _LETTERS_DIGITS.match(value)
        if not match:
            return _invalid(original, "missing allele fields or malformed format")
        locus_part, rest = match.group(1), match.group(2)

    locus = locus_part
    if not rest:
        return _invalid(original, "missing allele fields")

    if ":" in rest:
        fields = rest.split(":")
    else:
        if not rest.isdigit() or len(rest) % 2 != 0:
            return _invalid(original, f"malformed allele fields '{rest}'")
        fields = [rest[i : i + 2] for i in range(0, len(rest), 2)]

    if len(fields) < 2:
        return _invalid(original, "allele requires at least two fields")
    if any(not field.isdigit() for field in fields) or any(field == "" for field in fields):
        return _invalid(original, "allele fields must be numeric")

    fields = [fields[0].zfill(2), fields[1].zfill(2), *fields[2:]]
    normalized = f"HLA-{locus}*{':'.join(fields)}"

    klass = locus_class(locus)
    if klass is None:
        return _invalid(original, f"unknown HLA locus '{locus}'")

    declared = _canonical_class(declared_class)
    if declared_class is not None and declared is not None and declared not in ("I", "II"):
        return _invalid(original, f"unknown HLA class '{declared_class}'")
    if declared in ("I", "II") and declared != klass:
        return _invalid(
            original,
            f"class mismatch: locus {locus} is class {klass} but class {declared} was declared",
        )

    return HlaNormalization(
        raw=original,
        normalized=normalized,
        locus=locus,
        allele_class=klass,
        valid=True,
    )


def _normalize_header(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


# Header aliases accepted for the allele column (normalized form).
_ALLELE_HEADERS = {
    "allele",
    "hla",
    "hla_allele",
    "hla_allele_name",
    "allele_name",
    "allele_id",
    "value",
}
_CLASS_VALUES = {"I", "II", "1", "2"}


def _looks_like_allele(value: str | None) -> bool:
    """True when a cell itself looks like an HLA allele (used to detect a
    headerless allele list, so the first allele is never read as a header).

    A canonical allele always contains ``*``. A compact allele (e.g. ``A0201``)
    has a locus followed by at least two field digits — this deliberately does
    not match wide-format headers such as ``A1``/``B2``.
    """
    if not value:
        return False
    text = value.strip().upper()
    if "*" in text:
        return True
    return bool(re.match(r"^(HLA-)?[A-Z]{1,4}[0-9]{2,}$", text))


def _clean_lines(content: str) -> list[str]:
    """Strip a UTF-8 BOM, blank lines and ``#`` comment lines."""
    content = content.lstrip("\ufeff")
    return [
        line
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _record_from_mapping(row: dict) -> dict:
    normalized_keys = {_normalize_header(k): v for k, v in row.items() if k is not None}

    def pick(*names: str):
        for name in names:
            if name in normalized_keys and normalized_keys[name] not in (None, ""):
                return normalized_keys[name]
        return None

    confidence = pick("confidence")
    try:
        confidence_value = float(confidence) if confidence not in (None, "") else None
    except (TypeError, ValueError):
        confidence_value = None

    return {
        "allele": pick(
            "allele", "hla", "hla_allele", "hla_allele_name", "allele_name", "allele_id", "value"
        ),
        "declared_class": pick("class", "hla_class", "allele_class", "hla_type"),
        "source": pick("source"),
        "method": pick("method", "typing_method"),
        "confidence": confidence_value,
        "version": pick("version", "reference_version", "hla_version"),
    }


def map_hla_record(row: dict) -> dict:
    """Map a manual/JSON mapping onto the canonical record shape."""
    return _record_from_mapping(row)


def _parse_delimited(content: str, delimiter: str) -> list[dict]:
    """Parse CSV/TSV HLA content.

    Handles a UTF-8 BOM, blank lines and ``#`` comments, a recognized
    ``allele`` header, and headerless allele lists (one allele per row, or
    ``allele<TAB>class``). A file with a header but no recognizable allele
    column is reported explicitly instead of being read as empty alleles.
    """
    lines = _clean_lines(content)
    if not lines:
        return []
    matrix = [
        row
        for row in csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)
        if any(cell.strip() for cell in row)
    ]
    if not matrix:
        return []

    header = matrix[0]
    normalized_header = [_normalize_header(cell) for cell in header]
    if any(cell in _ALLELE_HEADERS for cell in normalized_header):
        return [_record_from_mapping(dict(zip(header, row))) for row in matrix[1:]]

    # No recognized header. If the first cell itself looks like an allele,
    # treat the whole matrix as a headerless allele list (never as a header).
    if _looks_like_allele(header[0] if header else None):
        records: list[dict] = []
        for row in matrix:
            allele = row[0] if row else None
            declared = None
            if len(row) >= 2 and row[1].strip().upper() in _CLASS_VALUES:
                declared = row[1]
            records.append({"allele": allele, "declared_class": declared})
        return records

    found = ", ".join(cell for cell in header if cell.strip())
    raise ValueError(
        "Could not locate an 'allele' column in the HLA file. "
        f"Found columns: {found or '(none)'}. Expected a column named "
        "'allele' (or 'hla_allele'), or a headerless allele list."
    )


def parse_hla_records(content: str, fmt: str) -> list[dict]:
    """Parse JSON / CSV / TSV HLA content into a list of raw records."""
    fmt = fmt.lower()
    if fmt == "json":
        data = json.loads(content.lstrip("\ufeff"))
        if isinstance(data, dict):
            rows = data.get("alleles") or data.get("hla") or data.get("records") or []
        elif isinstance(data, list):
            rows = data
        else:
            raise ValueError("Unsupported JSON structure for HLA input")
        return [_record_from_mapping(row) for row in rows if isinstance(row, dict)]

    if fmt == "csv":
        return _parse_delimited(content, ",")
    if fmt == "tsv":
        return _parse_delimited(content, "\t")

    raise ValueError(f"Unsupported HLA input format '{fmt}'")
