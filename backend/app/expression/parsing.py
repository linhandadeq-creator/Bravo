"""Parse expression CSV / TSV input into raw records."""
from __future__ import annotations

import csv
import io


def _normalize_header(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def _record_from_mapping(row: dict) -> dict:
    keys = {_normalize_header(k): v for k, v in row.items() if k is not None}

    def pick(*names: str):
        for name in names:
            if name in keys and keys[name] not in (None, ""):
                return keys[name]
        return None

    return {
        "gene_id": pick("gene_id", "geneid", "ensembl_gene_id", "ensg"),
        "gene_symbol": pick("gene_symbol", "symbol", "gene", "gene_name"),
        "transcript_id": pick("transcript_id", "transcriptid", "ensembl_transcript_id", "enst"),
        "expression_value": pick("expression_value", "expression", "tpm", "fpkm", "value", "counts"),
        "unit": pick("unit", "units"),
        "source": pick("source"),
        "level": pick("level", "expression_level"),
    }


def map_expression_record(row: dict) -> dict:
    return _record_from_mapping(row)


def _clean_lines(content: str) -> list[str]:
    """Strip a UTF-8 BOM, blank lines and ``#`` comment lines.

    Expression exports commonly start with a ``#`` provenance/notice line;
    feeding it to DictReader would make it the header and blank every field.
    """
    content = content.lstrip("\ufeff")
    return [
        line
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def parse_expression_records(content: str, fmt: str) -> list[dict]:
    fmt = fmt.lower()
    if fmt not in ("csv", "tsv"):
        raise ValueError(f"Unsupported expression input format '{fmt}'")
    delimiter = "," if fmt == "csv" else "\t"
    lines = _clean_lines(content)
    if not lines:
        return []
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    return [_record_from_mapping(row) for row in reader]
