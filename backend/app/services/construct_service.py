"""Construct builder service: selection, ordering, QC, locking and export."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun
from app.models.construct import (
    CONSTRUCT_DRAFT,
    CONSTRUCT_INVALID,
    CONSTRUCT_LOCKED,
    CONSTRUCT_VALIDATED,
    ConstructItem,
    SimulationConstruct,
)
from app.models.neoantigen import NeoantigenCandidate
from app.blueprint.design import DesignConfig, design_construct
from app.blueprint.formats import resolve_format
from app.blueprint.package import augment_package
from app.blueprint.sequence_qc import evaluate_sequence
from app.simulation.production import build_production_package
from app.simulation.qc import VALIDATED_SIMULATION, evaluate_construct
from app.simulation.representation import (
    build_ordering,
    build_representation,
)


class ConstructError(RuntimeError):
    pass


def _candidate_version(candidate: NeoantigenCandidate | None) -> str | None:
    if candidate is None or candidate.updated_at is None:
        return None
    return candidate.updated_at.isoformat()


def _load_candidates(db: Session, ids: list[str]) -> dict[str, NeoantigenCandidate]:
    if not ids:
        return {}
    rows = (
        db.execute(select(NeoantigenCandidate).where(NeoantigenCandidate.id.in_(ids)))
        .scalars()
        .all()
    )
    return {row.id: row for row in rows}


def _qc_to_dict(qc) -> dict:
    return {
        "status": qc.status,
        "candidate_count": qc.candidate_count,
        "checks": [
            {"id": c.id, "label": c.label, "status": c.status, "detail": c.detail}
            for c in qc.checks
        ],
        "traceability": qc.traceability,
        "errors": qc.errors,
    }


def rebuild_construct(
    db: Session,
    construct: SimulationConstruct,
    run: AnalysisRun,
    selected_by: str | None,
) -> SimulationConstruct:
    candidate_ids = list(construct.candidate_ids or [])
    fmt = resolve_format(construct.simulation_format)
    ordering = build_ordering(len(candidate_ids))
    construct.ordering = ordering
    construct.construct_representation = (
        build_representation(len(candidate_ids), fmt) if candidate_ids else None
    )

    candidates_map = _load_candidates(db, candidate_ids)
    ordered = [candidates_map[cid] for cid in candidate_ids if cid in candidates_map]
    peptides = [c.peptide_sequence for c in ordered if c.peptide_sequence]
    designed = design_construct(peptides, DesignConfig(format=fmt)) if peptides else None
    construct.sequence = designed.rna if designed else None

    now = datetime.now(timezone.utc)
    db.execute(
        delete(ConstructItem).where(ConstructItem.construct_id == construct.id)
    )
    for index, candidate_id in enumerate(candidate_ids):
        candidate = candidates_map.get(candidate_id)
        db.add(
            ConstructItem(
                construct_id=construct.id,
                candidate_id=candidate_id,
                position=index + 1,
                label=ordering[index]["label"],
                spacer=ordering[index]["spacer"],
                selected_by=selected_by,
                selected_at=now,
                candidate_version=_candidate_version(candidate),
            )
        )

    construct.selected_by = selected_by
    construct.selected_at = now
    first = candidates_map.get(candidate_ids[0]) if candidate_ids else None
    construct.candidate_version = _candidate_version(first)

    qc = evaluate_construct(db, run, candidate_ids, ordering)
    qc_dict = _qc_to_dict(qc)
    sequence_qc = None
    if designed is not None:
        sequence_qc = evaluate_sequence(designed)
        qc_dict["sequence_qc"] = sequence_qc.as_dict()
    construct.qc_summary = qc_dict
    construct.validation = qc_dict
    construct.status = qc.status if candidate_ids else CONSTRUCT_DRAFT

    if candidate_ids and designed is not None and sequence_qc is not None:
        package = build_production_package(construct, run, ordered)
        construct.simulation_output = augment_package(package, designed, sequence_qc)
    else:
        construct.simulation_output = None
    db.commit()
    db.refresh(construct)
    return construct


def create_construct(
    db: Session,
    run: AnalysisRun,
    candidate_ids: list[str],
    name: str,
    simulation_format: str,
    selected_by: str | None,
) -> SimulationConstruct:
    fmt = resolve_format(simulation_format)
    construct = SimulationConstruct(
        analysis_run_id=run.id,
        name=name,
        simulation_format=fmt,
        candidate_ids=list(candidate_ids),
    )
    db.add(construct)
    db.commit()
    db.refresh(construct)
    return rebuild_construct(db, construct, run, selected_by)


def get_construct(db: Session, construct_id: str) -> SimulationConstruct:
    construct = db.get(SimulationConstruct, construct_id)
    if construct is None:
        raise ConstructError("Construct not found")
    return construct


def list_constructs(db: Session, analysis_run_id: str) -> list[SimulationConstruct]:
    statement = (
        select(SimulationConstruct)
        .where(SimulationConstruct.analysis_run_id == analysis_run_id)
        .order_by(SimulationConstruct.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


def _assert_editable(construct: SimulationConstruct) -> None:
    if construct.status == CONSTRUCT_LOCKED:
        raise ConstructError("Construct is LOCKED and can no longer be edited.")


def update_selection(
    db: Session,
    construct: SimulationConstruct,
    candidate_ids: list[str],
    selected_by: str | None,
) -> SimulationConstruct:
    _assert_editable(construct)
    run = db.get(AnalysisRun, construct.analysis_run_id)
    construct.candidate_ids = list(candidate_ids)
    db.commit()
    db.refresh(construct)
    return rebuild_construct(db, construct, run, selected_by or construct.selected_by)


def validate_construct(
    db: Session, construct: SimulationConstruct
) -> SimulationConstruct:
    run = db.get(AnalysisRun, construct.analysis_run_id)
    if construct.status == CONSTRUCT_LOCKED:
        return construct
    construct = rebuild_construct(db, construct, run, construct.selected_by)
    if not construct.candidate_ids:
        construct.status = CONSTRUCT_INVALID
        db.commit()
        db.refresh(construct)
    return construct


def lock_construct(
    db: Session, construct: SimulationConstruct
) -> SimulationConstruct:
    if construct.status == CONSTRUCT_LOCKED:
        return construct
    if construct.status != CONSTRUCT_VALIDATED:
        raise ConstructError(
            "Only a VALIDATED_SIMULATION construct can be locked."
        )
    construct.status = CONSTRUCT_LOCKED
    db.commit()
    db.refresh(construct)
    return construct


def _serialize(construct: SimulationConstruct, db: Session) -> dict:
    candidates_map = _load_candidates(db, list(construct.candidate_ids or []))
    items = [
        {
            "position": item.position,
            "label": item.label,
            "candidate_id": item.candidate_id,
            "spacer": item.spacer,
            "selected_by": item.selected_by,
            "selected_at": item.selected_at.isoformat() if item.selected_at else None,
            "candidate_version": item.candidate_version,
            "gene": candidates_map.get(item.candidate_id).gene
            if candidates_map.get(item.candidate_id)
            else None,
            "protein_change": candidates_map.get(item.candidate_id).protein_change
            if candidates_map.get(item.candidate_id)
            else None,
            "hla_allele": candidates_map.get(item.candidate_id).hla_allele
            if candidates_map.get(item.candidate_id)
            else None,
        }
        for item in (construct.items or [])
    ]
    return {
        "construct_id": construct.id,
        "analysis_run_id": construct.analysis_run_id,
        "name": construct.name,
        "simulation_format": construct.simulation_format,
        "status": construct.status,
        "candidate_ids": construct.candidate_ids or [],
        "ordering": construct.ordering or [],
        "construct_representation": construct.construct_representation,
        "sequence_length": len(construct.sequence or ""),
        "selected_by": construct.selected_by,
        "selected_at": construct.selected_at.isoformat() if construct.selected_at else None,
        "candidate_version": construct.candidate_version,
        "created_at": construct.created_at.isoformat() if construct.created_at else None,
        "items": items,
        "qc": construct.qc_summary,
        "production_package": construct.simulation_output,
    }


def export_construct(
    db: Session, construct: SimulationConstruct, fmt: str
) -> tuple[str, str, str]:
    payload = _serialize(construct, db)
    stem = f"construct_{construct.id[:8]}"

    if fmt == "json":
        return (
            json.dumps(payload, indent=2),
            "application/json",
            f"{stem}.json",
        )

    if fmt == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["position", "label", "candidate_id", "gene", "protein_change", "hla_allele", "spacer", "candidate_version"])
        for item in payload["items"]:
            writer.writerow([
                item["position"],
                item["label"],
                item["candidate_id"],
                item["gene"],
                item["protein_change"],
                item["hla_allele"],
                item["spacer"],
                item["candidate_version"],
            ])
        return buffer.getvalue(), "text/csv", f"{stem}.csv"

    if fmt == "report":
        package = construct.simulation_output or {}
        lines = [
            "# mRNA Construct Research Report (SIMULATION)",
            "",
            f"**{package.get('disclaimer', 'RESEARCH SIMULATION ONLY.')}**",
            "",
            f"- Construct ID: `{construct.id}`",
            f"- Analysis run: `{construct.analysis_run_id}`",
            f"- Simulation format: {construct.simulation_format}",
            f"- Status: {construct.status}",
            f"- Candidates: {len(construct.candidate_ids or [])}",
            f"- Sequence length (simulated): {len(construct.sequence or '')} nt",
            "",
            "## Construct representation",
            "",
            "```",
            construct.construct_representation or "(empty)",
            "```",
            "",
            "## Antigen ordering",
            "",
            "| # | Label | Candidate | Gene | Mutation | HLA |",
            "|---|-------|-----------|------|----------|-----|",
        ]
        for item in payload["items"]:
            lines.append(
                f"| {item['position']} | {item['label']} | `{(item['candidate_id'] or '')[:8]}` | "
                f"{item['gene'] or '—'} | {item['protein_change'] or '—'} | {item['hla_allele'] or '—'} |"
            )
        lines += ["", "## Validation", ""]
        for check in (construct.qc_summary or {}).get("checks", []):
            lines.append(f"- [{check['status']}] {check['label']}: {check['detail']}")
        lines += ["", "## Traceability", ""]
        for trace in (construct.qc_summary or {}).get("traceability", []):
            chain = " → ".join(
                f"{step['step']}:{step['id'][:8] if step['id'] else 'MISSING'}"
                for step in trace["steps"]
            )
            lines.append(f"- {chain}")
        lines += ["", "## Production sections (simulation)", ""]
        for key, section in (package.get("sections") or {}).items():
            lines.append(f"### {section.get('title', key)}")
            lines.append("")
            lines.append(f"```json\n{json.dumps(section, indent=2)}\n```")
            lines.append("")
        return "\n".join(lines), "text/markdown", f"{stem}.md"

    raise ConstructError(f"Unsupported export format '{fmt}'")
