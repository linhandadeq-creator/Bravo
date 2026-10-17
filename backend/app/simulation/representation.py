"""Abstract construct representation and simulated nucleic-acid design.

The representation uses abstract tokens:

    [5PRIME] [ANTIGEN_001] [SPACER] [ANTIGEN_002] ... [3PRIME]      (mRNA-LNP)
    [PIE_3P] [IRES] [ANTIGEN_001] [SPACER] ... [PIE_5P]             (circRNA)
    [5PRIME] [REPLICASE] [SGP] [ANTIGEN_001] [SPACER] ... [3PRIME]  (saRNA)

The generated sequence is a **research simulation** assembled from mock peptide
data. It is not a validated therapeutic design and is not for clinical use.
"""
from __future__ import annotations

from app.blueprint.formats import (
    FORMAT_CIRCRNA,
    FORMAT_MRNA_LNP,
    FORMAT_SARNA,
    resolve_format,
)

TOKEN_5PRIME = "[5PRIME]"
TOKEN_3PRIME = "[3PRIME]"
SPACER_TOKEN = "[SPACER]"
TOKEN_PIE_3P = "[PIE_3P]"
TOKEN_IRES = "[IRES]"
TOKEN_PIE_5P = "[PIE_5P]"
TOKEN_REPLICASE = "[REPLICASE]"
TOKEN_SGP = "[SGP]"
LINKER_SEQUENCE = "GGCGGCGGCGGCAGC"  # (Gly-Gly-Gly-Gly-Ser)2 linker, simulated

# Human-preferred (highest-usage) codons — a simple, deterministic codon
# optimisation for the simulated construct. DNA form; converted to RNA on output.
# (Kazusa human codon usage: the most frequent codon for each residue.)
HUMAN_PREFERRED_CODON = {
    "A": "GCC",
    "R": "AGG",
    "N": "AAC",
    "D": "GAC",
    "C": "TGC",
    "Q": "CAG",
    "E": "GAG",
    "G": "GGC",
    "H": "CAC",
    "I": "ATC",
    "L": "CTG",
    "K": "AAG",
    "M": "ATG",
    "F": "TTC",
    "P": "CCC",
    "S": "AGC",
    "T": "ACC",
    "W": "TGG",
    "Y": "TAC",
    "V": "GTG",
}


def antigen_label(position: int) -> str:
    return f"ANTIGEN_{position:03d}"


def build_ordering(count: int) -> list[dict]:
    """Return the ordered construct items with spacer placement."""
    ordering: list[dict] = []
    for position in range(1, count + 1):
        ordering.append(
            {
                "position": position,
                "label": antigen_label(position),
                "spacer": SPACER_TOKEN if position < count else None,
            }
        )
    return ordering


def _edge_tokens(fmt: str) -> tuple[list[str], list[str]]:
    if fmt == FORMAT_CIRCRNA:
        return [TOKEN_PIE_3P, TOKEN_IRES], [TOKEN_PIE_5P]
    if fmt == FORMAT_SARNA:
        return [TOKEN_5PRIME, TOKEN_REPLICASE, TOKEN_SGP], [TOKEN_3PRIME]
    return [TOKEN_5PRIME], [TOKEN_3PRIME]


def build_representation(count: int, simulation_format: str = FORMAT_MRNA_LNP) -> str:
    fmt = resolve_format(simulation_format)
    pre, post = _edge_tokens(fmt)
    tokens = list(pre)
    for position in range(1, count + 1):
        tokens.append(f"[{antigen_label(position)}]")
        if position < count:
            tokens.append(SPACER_TOKEN)
    tokens.extend(post)
    return " ".join(tokens)


def _encode_peptide(peptide: str) -> str:
    codons = [
        HUMAN_PREFERRED_CODON[residue]
        for residue in peptide.upper()
        if residue in HUMAN_PREFERRED_CODON
    ]
    return "".join(codons).replace("T", "U")


def simulate_sequence(
    peptides: list[str | None], simulation_format: str = FORMAT_MRNA_LNP
) -> str | None:
    """Design a manufacturing-oriented mRNA sequence via the constraint engine.

    Returns the RNA sequence (or ``None`` when there are no peptides).
    """
    from app.blueprint.design import DesignConfig, design_construct

    cleaned = [p for p in peptides if p]
    if not cleaned:
        return None
    fmt = resolve_format(simulation_format)
    return design_construct(cleaned, DesignConfig(format=fmt)).rna
