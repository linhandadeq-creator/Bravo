"""Simulation QC and traceability for mRNA constructs."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun
from app.models.annotation import VariantAnnotation
from app.models.neoantigen import (
    PREDICTION_AVAILABLE,
    PREDICTION_MOCK,
    CANDIDATE_RANKED,
    NeoantigenCandidate,
    PredictionResult,
)
from app.models.variant import Variant
from app.simulation.representation import antigen_label

CHECK_PASS = "pass"
CHECK_WARN = "warn"
CHECK_FAIL = "fail"

VALIDATED_SIMULATION = "VALIDATED_SIMULATION"
INVALID = "INVALID"


@dataclass
class ConstructCheck:
    id: str
    label: str
    status: str
    detail: str


@dataclass
class ConstructQc:
    status: str
    checks: list[ConstructCheck] = field(default_factory=list)
    traceability: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    candidate_count: int = 0


def _check(checks, errors, identifier, label, ok, detail, fail_status=CHECK_FAIL):
    checks.append(
        ConstructCheck(
            id=identifier,
            label=label,
            status=CHECK_PASS if ok else fail_status,
            detail=detail,
        )
    )
    if not ok:
        errors.append(detail)


def _load_candidates(db: Session, candidate_ids: list[str]) -> dict[str, NeoantigenCandidate]:
    if not candidate_ids:
        return {}
    statement = select(NeoantigenCandidate).where(
        NeoantigenCandidate.id.in_(candidate_ids)
    )
    return {c.id: c for c in db.execute(statement).scalars().all()}


def _provenance_chain(db: Session, candidate: NeoantigenCandidate) -> tuple[list[dict], bool]:
    steps: list[dict] = [
        {
            "step": "candidate",
            "id": candidate.id,
            "label": candidate.gene or candidate.peptide_representation,
            "ok": True,
        }
    ]

    variant = db.get(Variant, candidate.variant_id) if candidate.variant_id else None
    steps.append(
        {
            "step": "variant",
            "id": variant.id if variant else None,
            "label": (
                f"{variant.chromosome_normalized or variant.chromosome}:{variant.position} "
                f"{variant.reference}>{variant.alternate}"
                if variant
                else None
            ),
            "ok": variant is not None,
        }
    )

    annotation = None
    if variant is not None:
        annotation = (
            db.execute(
                select(VariantAnnotation)
                .where(VariantAnnotation.variant_id == variant.id)
                .order_by(VariantAnnotation.created_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
    steps.append(
        {
            "step": "annotation",
            "id": annotation.id if annotation else None,
            "label": (
                f"{annotation.consequence} {annotation.protein_change or ''}".strip()
                if annotation
                else None
            ),
            "ok": annotation is not None,
        }
    )

    steps.append(
        {
            "step": "hla",
            "id": candidate.hla_profile_id,
            "label": candidate.hla_allele,
            "ok": bool(candidate.hla_allele),
        }
    )

    prediction = (
        db.execute(
            select(PredictionResult)
            .where(PredictionResult.candidate_id == candidate.id)
            .order_by(PredictionResult.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    steps.append(
        {
            "step": "prediction",
            "id": prediction.id if prediction else None,
            "label": (
                f"{prediction.provider}:{prediction.metric_name}={prediction.prediction_value}"
                if prediction
                else None
            ),
            "ok": prediction is not None,
        }
    )

    ranking_ok = candidate.status == CANDIDATE_RANKED and candidate.ranking_score is not None
    steps.append(
        {
            "step": "ranking",
            "id": candidate.ranking_configuration_id,
            "label": f"score={candidate.ranking_score}" if ranking_ok else None,
            "ok": ranking_ok,
        }
    )

    return steps, all(step["ok"] for step in steps)


def evaluate_construct(
    db: Session,
    run: AnalysisRun,
    candidate_ids: list[str],
    ordering: list[dict] | None = None,
) -> ConstructQc:
    checks: list[ConstructCheck] = []
    errors: list[str] = []

    candidates = _load_candidates(db, candidate_ids)
    candidate_count = len(candidate_ids)

    # ---- existence ---------------------------------------------------------
    missing = [cid for cid in candidate_ids if cid not in candidates]
    _check(
        checks,
        errors,
        "candidate_exists",
        "Candidate exists",
        not missing,
        f"Missing candidate(s): {', '.join(missing)}" if missing else "All candidates found.",
    )

    # ---- duplicates --------------------------------------------------------
    duplicates = {cid for cid in candidate_ids if candidate_ids.count(cid) > 1}
    _check(
        checks,
        errors,
        "duplicate_candidates",
        "No duplicates",
        not duplicates,
        f"Duplicate candidate(s): {', '.join(sorted(duplicates))}"
        if duplicates
        else "No duplicate candidates.",
    )

    # ---- same run ----------------------------------------------------------
    wrong_run = [
        c.id for c in candidates.values() if c.analysis_run_id != run.id
    ]
    _check(
        checks,
        errors,
        "same_analysis_run",
        "Belongs to current AnalysisRun",
        not wrong_run,
        f"Candidate(s) from another run: {', '.join(wrong_run)}"
        if wrong_run
        else "All candidates belong to the current run.",
    )

    # ---- HLA / prediction / ranking / peptide ------------------------------
    ordered_candidates = [candidates[cid] for cid in candidate_ids if cid in candidates]

    missing_hla = [c.id for c in ordered_candidates if not c.hla_allele]
    _check(
        checks,
        errors,
        "hla_information",
        "HLA information",
        not missing_hla,
        f"Candidate(s) without HLA: {', '.join(missing_hla)}"
        if missing_hla
        else "HLA present for all candidates.",
    )

    bad_prediction = [
        c.id
        for c in ordered_candidates
        if c.prediction_status not in (PREDICTION_MOCK, PREDICTION_AVAILABLE)
    ]
    _check(
        checks,
        errors,
        "prediction_status",
        "Prediction status",
        not bad_prediction,
        "PREDICTION UNAVAILABLE for candidate(s): " + ", ".join(bad_prediction)
        if bad_prediction
        else "All candidates have a prediction.",
    )

    bad_ranking = [
        c.id
        for c in ordered_candidates
        if c.status != CANDIDATE_RANKED or c.ranking_score is None
    ]
    _check(
        checks,
        errors,
        "ranking_status",
        "Ranking status",
        not bad_ranking,
        "Unranked candidate(s): " + ", ".join(bad_ranking)
        if bad_ranking
        else "All candidates are ranked.",
    )

    missing_peptide = [c.id for c in ordered_candidates if not c.peptide_sequence]
    _check(
        checks,
        errors,
        "missing_data",
        "Missing data",
        not missing_peptide,
        f"Candidate(s) missing peptide data: {', '.join(missing_peptide)}"
        if missing_peptide
        else "No missing candidate data.",
    )

    # ---- provenance / traceability ----------------------------------------
    traceability: list[dict] = []
    provenance_errors: list[str] = []
    for candidate in ordered_candidates:
        steps, ok = _provenance_chain(db, candidate)
        traceability.append({"candidate_id": candidate.id, "ok": ok, "steps": steps})
        if not ok:
            provenance_errors.append(candidate.id)
    _check(
        checks,
        errors,
        "provenance",
        "Complete provenance",
        not provenance_errors,
        f"Incomplete provenance for: {', '.join(provenance_errors)}"
        if provenance_errors
        else "Candidate → Variant → Annotation → HLA → Prediction → Ranking is complete.",
    )

    # ---- ordering ----------------------------------------------------------
    if ordering is None:
        ordering = [
            {"position": i + 1, "label": antigen_label(i + 1)} for i in range(candidate_count)
        ]
    positions = [item.get("position") for item in ordering]
    labels = [item.get("label") for item in ordering]
    ordering_ok = (
        len(ordering) == candidate_count
        and positions == list(range(1, candidate_count + 1))
        and labels == [antigen_label(i) for i in range(1, candidate_count + 1)]
    )
    _check(
        checks,
        errors,
        "construct_ordering",
        "Construct ordering",
        ordering_ok,
        "Ordering is contiguous, unique and labelled ANTIGEN_001..N."
        if ordering_ok
        else "Ordering must be contiguous 1..N with ANTIGEN_001..N labels.",
    )

    # ---- non-empty ---------------------------------------------------------
    _check(
        checks,
        errors,
        "candidate_selection",
        "Candidate selection",
        candidate_count > 0,
        "No candidates selected." if candidate_count == 0 else f"{candidate_count} candidate(s) selected.",
    )

    status = VALIDATED_SIMULATION if not errors else INVALID
    return ConstructQc(
        status=status,
        checks=checks,
        traceability=traceability,
        errors=errors,
        candidate_count=candidate_count,
    )
