"""Experimental-design worklist derived from construct candidates."""
from __future__ import annotations

import csv
import io

CONTROL_ROWS = [
    {
        "role": "control_positive",
        "gene": "CONTROL",
        "protein_change": "common immunogen",
        "hla_allele": "",
        "peptide": "SIINFEKL",
        "note": "Generic positive-control peptide (example); replace per experimental system.",
    },
    {
        "role": "control_negative",
        "gene": "CONTROL",
        "protein_change": "irrelevant",
        "hla_allele": "",
        "peptide": "GILGFVFTL",
        "note": "Irrelevant / negative-control peptide (example).",
    },
]

COLUMNS = [
    "position",
    "label",
    "candidate_id",
    "gene",
    "protein_change",
    "hla_allele",
    "hla_class",
    "peptide",
    "binding_affinity",
    "processing_score",
    "presentation_score",
    "ranking_score",
    "self_similar",
    "ms_evidence",
    "status",
    "role",
    "note",
]


def build_worklist(
    construct, candidates_by_id: dict, predictions_by_candidate: dict | None = None
) -> list[dict]:
    predictions_by_candidate = predictions_by_candidate or {}
    rows: list[dict] = []
    for item in construct.items or []:
        candidate = candidates_by_id.get(item.candidate_id or "")
        prediction = predictions_by_candidate.get(item.candidate_id or "")
        detail = prediction.detail if prediction is not None and prediction.detail else {}
        mutation = (candidate.mutation_evidence or {}) if candidate else {}
        rows.append(
            {
                "position": item.position,
                "label": item.label,
                "candidate_id": item.candidate_id,
                "gene": getattr(candidate, "gene", None),
                "protein_change": getattr(candidate, "protein_change", None),
                "hla_allele": getattr(candidate, "hla_allele", None),
                "hla_class": getattr(candidate, "hla_class", None),
                "peptide": detail.get("peptide")
                or getattr(candidate, "peptide_sequence", None),
                "binding_affinity": detail.get("binding_affinity"),
                "processing_score": detail.get("processing_score"),
                "presentation_score": detail.get("presentation_score"),
                "ranking_score": getattr(candidate, "ranking_score", None),
                "self_similar": mutation.get("self_similar", False),
                "ms_evidence": (mutation.get("ms_evidence") or {}).get("kind") or "",
                "status": getattr(candidate, "status", None),
                "role": "candidate",
                "note": "",
            }
        )
    rows.extend(CONTROL_ROWS)
    return rows


def worklist_csv(rows: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({col: row.get(col, "") for col in COLUMNS})
    return buffer.getvalue()
