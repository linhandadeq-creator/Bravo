"""RNA-seq expression-matrix quantification (v1).

Takes a genes × samples matrix (tumor and normal columns) and computes group
means plus a tumor-vs-normal log2 fold change with an explicit pseudocount.
This is a matrix-level quantification — no read alignment is performed (a full
aligner-based pipeline is a future phase). Every step records its provenance;
missing data is reported, never fabricated.

Conventions (documented, transparent):
- group value = arithmetic mean of the group's samples (raw units)
- log2_fold_change = log2((tumor + pc) / (normal + pc)) with pseudocount pc=1
- is_expressed = tumor >= threshold (default 1.0, e.g. TPM)
- differentially_expressed = is_expressed and |log2_fold_change| >= 1.0
"""
from __future__ import annotations

import csv
import io
import math

QUANTIFICATION_METHOD = "rnaseq-matrix-v1"
QUANTIFICATION_VERSION = "1.0.0"
DEFAULT_PSEUDOCOUNT = 1.0
DEFAULT_EXPRESSION_THRESHOLD = 1.0
DEFAULT_LOG2FC_THRESHOLD = 1.0

PAIRED_VALUE_COLUMNS = (
    ("tumor_tpm", "normal_tpm"),
    ("tumor_value", "normal_value"),
    ("tumor_counts", "normal_counts"),
    ("tumor", "normal"),
    ("tumor_fpkm", "normal_fpkm"),
)

_ID_COLUMNS = ("gene_id", "geneid", "ensembl_gene_id", "ensg")
_SYMBOL_COLUMNS = ("gene_symbol", "symbol", "gene", "gene_name")


def _norm(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def _first(keys: dict, *names: str):
    for name in names:
        if name in keys and keys[name] not in (None, ""):
            return keys[name]
    return None


def parse_expression_matrix(
    content: str,
    fmt: str,
    tumor_samples: list[str] | None = None,
    normal_samples: list[str] | None = None,
) -> tuple[list[dict], dict]:
    """Parse a genes × samples matrix.

    Returns (rows, layout) where each row is
    ``{gene_id, gene_symbol, tumor_value, normal_value, unit}`` and layout
    describes the matched column scheme. Explicit paired columns
    (``tumor_tpm``/``normal_tpm`` ...) take precedence; otherwise the sample
    names given in ``tumor_samples`` / ``normal_samples`` select columns.
    """
    fmt = fmt.lower()
    if fmt not in ("csv", "tsv"):
        raise ValueError(f"Unsupported expression matrix format '{fmt}'")
    delimiter = "," if fmt == "csv" else "\t"
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    header = [h for h in (reader.fieldnames or []) if h is not None]
    keys = {_norm(h): h for h in header}

    gene_key = _first(keys, *_ID_COLUMNS)
    symbol_key = _first(keys, *_SYMBOL_COLUMNS)

    paired = next(
        (
            (keys[t], keys[n])
            for t, n in PAIRED_VALUE_COLUMNS
            if t in keys and n in keys
        ),
        None,
    )

    tumor_cols: list[str] = []
    normal_cols: list[str] = []
    layout: dict
    if paired:
        tumor_cols, normal_cols = [paired[0]], [paired[1]]
        layout = {"scheme": "paired_columns", "tumor": [paired[0]], "normal": [paired[1]]}
    else:
        requested_tumor = [s.strip() for s in (tumor_samples or []) if s.strip()]
        requested_normal = [s.strip() for s in (normal_samples or []) if s.strip()]
        for sample in requested_tumor:
            if sample not in header:
                raise ValueError(f"Tumor sample column '{sample}' not found in matrix header")
            tumor_cols.append(sample)
        for sample in requested_normal:
            if sample not in header:
                raise ValueError(f"Normal sample column '{sample}' not found in matrix header")
            normal_cols.append(sample)
        if not tumor_cols or not normal_cols:
            raise ValueError(
                "Matrix has no paired tumor/normal columns; provide "
                "tumor_samples and normal_samples (comma-separated column names)."
            )
        layout = {"scheme": "sample_columns", "tumor": tumor_cols, "normal": normal_cols}

    rows: list[dict] = []
    for record in reader:
        gene_id = record.get(gene_key) if gene_key else None
        symbol = record.get(symbol_key) if symbol_key else None
        if not gene_id and not symbol:
            continue
        tumor_values = [record.get(col) for col in tumor_cols]
        normal_values = [record.get(col) for col in normal_cols]

        def mean(values: list) -> float | None:
            numbers = []
            for value in values:
                if value in (None, ""):
                    continue
                try:
                    numbers.append(float(value))
                except ValueError:
                    raise ValueError(
                        f"Non-numeric matrix value '{value}' for gene "
                        f"{gene_id or symbol}"
                    ) from None
            return round(sum(numbers) / len(numbers), 6) if numbers else None

        rows.append(
            {
                "gene_id": gene_id,
                "gene_symbol": symbol,
                "tumor_value": mean(tumor_values),
                "normal_value": mean(normal_values),
            }
        )
    return rows, layout


def quantify(
    rows: list[dict],
    pseudocount: float = DEFAULT_PSEUDOCOUNT,
    expression_threshold: float = DEFAULT_EXPRESSION_THRESHOLD,
    log2fc_threshold: float = DEFAULT_LOG2FC_THRESHOLD,
) -> list[dict]:
    """Compute tumor/normal log2 fold change and expression calls."""
    results: list[dict] = []
    for row in rows:
        tumor = row.get("tumor_value")
        normal = row.get("normal_value")
        if tumor is None:
            results.append(
                {
                    **row,
                    "log2_fold_change": None,
                    "is_expressed": False,
                    "differentially_expressed": False,
                    "note": "missing tumor value",
                }
            )
            continue
        if normal is None:
            # Tumor present, normal absent: honest convention — treat the
            # log2FC as log2(tumor + pc) with an explicit note (no silent 0).
            log2fc = round(math.log2(tumor + pseudocount), 6)
            results.append(
                {
                    **row,
                    "log2_fold_change": log2fc,
                    "is_expressed": tumor >= expression_threshold,
                    "differentially_expressed": False,
                    "note": "normal sample absent; log2FC computed as log2(tumor+pc)",
                }
            )
            continue
        log2fc = round(
            math.log2((tumor + pseudocount) / (normal + pseudocount)), 6
        )
        is_expressed = tumor >= expression_threshold
        differentially_expressed = is_expressed and abs(log2fc) >= log2fc_threshold
        results.append(
            {
                **row,
                "log2_fold_change": log2fc,
                "is_expressed": is_expressed,
                "differentially_expressed": differentially_expressed,
                "note": None,
            }
        )
    return results
