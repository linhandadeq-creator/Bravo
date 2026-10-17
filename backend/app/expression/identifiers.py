"""Gene and transcript identifier normalization.

Normalization is explicit and auditable: every record stores whether an
identifier changed and which method produced the normalized value. Unknown
identifiers are preserved as-is and marked unresolved — identifiers are never
fabricated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

GENE_ID_NORMALIZATION_METHOD = "gene-id-normalizer-v1"
TRANSCRIPT_ID_NORMALIZATION_METHOD = "transcript-id-normalizer-v1"

_ENSG_RE = re.compile(r"^ENSG\d{11}$")
_ENST_RE = re.compile(r"^ENST\d{11}$")

# Small research symbol -> Ensembl map (mock reference). Extendable.
GENE_SYMBOL_TO_ID = {
    "MOCKGENE1": "ENSG_MOCK00001",
    "MOCKGENE2": "ENSG_MOCK00002",
    "TP53": "ENSG00000141510",
    "KRAS": "ENSG00000133703",
    "EGFR": "ENSG00000146648",
    "BRCA1": "ENSG00000012048",
    "BRCA2": "ENSG00000139618",
    "HLA-A": "ENSG00000206503",
    "HLA-B": "ENSG00000234745",
    "HLA-C": "ENSG00000204525",
}
GENE_ID_TO_SYMBOL = {value: key for key, value in GENE_SYMBOL_TO_ID.items()}


@dataclass
class IdNormalization:
    raw: str | None
    normalized: str | None
    changed: bool
    resolved: bool
    method: str | None


def _is_ensg(value: str) -> bool:
    return bool(_ENSG_RE.match(value)) or value.startswith("ENSG_MOCK")


def normalize_gene_id(
    raw: str | None, gene_symbol: str | None = None
) -> IdNormalization:
    value = (raw or "").strip()
    if value:
        base = value.split(".")[0].upper()
        changed = base != value
        if _is_ensg(base):
            return IdNormalization(
                raw=value,
                normalized=base,
                changed=changed,
                resolved=True,
                method=(
                    "ensembl-gene-version-strip" if changed else "ensembl-gene"
                ),
            )

    symbol = (gene_symbol or value).strip().upper()
    if symbol in GENE_SYMBOL_TO_ID:
        mapped = GENE_SYMBOL_TO_ID[symbol]
        return IdNormalization(
            raw=value or None,
            normalized=mapped,
            changed=mapped != value,
            resolved=True,
            method="gene-symbol-to-ensembl",
        )

    if not value:
        return IdNormalization(raw=None, normalized=None, changed=False, resolved=False, method=None)
    return IdNormalization(
        raw=value,
        normalized=value.upper(),
        changed=value.upper() != value,
        resolved=False,
        method="unresolved",
    )


def normalize_transcript_id(raw: str | None) -> IdNormalization:
    value = (raw or "").strip()
    if not value:
        return IdNormalization(raw=None, normalized=None, changed=False, resolved=False, method=None)
    base = value.split(".")[0].upper()
    changed = base != value
    return IdNormalization(
        raw=value,
        normalized=base,
        changed=changed,
        resolved=bool(_ENST_RE.match(base)),
        method=(
            "ensembl-transcript-version-strip" if changed else "ensembl-transcript"
        ),
    )
