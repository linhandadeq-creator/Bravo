"""Neoantigen Candidate Engine.

Data flow: SomaticCandidate + Annotation + HLA + Expression + Mutation Evidence
→ NeoantigenCandidate → Prediction → Ranking.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.annotation.base import AnnotationStatus
from app.annotation.mock import MOCK_TRANSCRIPTS, translate
from app.models.analysis_run import AnalysisRun
from app.models.annotation import VariantAnnotation
from app.models.expression import ExpressionRecord
from app.models.hla import HLAProfile
from app.models.neoantigen import (
    CANDIDATE_GENERATED,
    CANDIDATE_PREDICTED,
    CANDIDATE_RANKED,
    CANDIDATE_REJECTED,
    CANDIDATE_UNCERTAIN,
    PREDICTION_MOCK,
    PREDICTION_PENDING,
    PREDICTION_UNAVAILABLE,
    NeoantigenCandidate,
    PredictionResult,
    RankingConfiguration,
)
from app.models.somatic_candidate import SomaticCandidate
from app.models.variant import Variant
from app.prediction import (
    PredictionInput,
    ProviderStatus,
    get_prediction_provider,
)
from app.prediction.registry import UnknownPredictionProviderError
from app.ranking.engine import (
    DEFAULT_WEIGHTS,
    DISCLAIMER,
    CandidateRankingEngine,
    RankingInput,
    specificity_from_classification,
)
from app.services.annotation_engine import (
    AnnotationGateError,
    require_traceable_annotations,
)
from app.services.expression_service import EXPRESSION_AVAILABLE, expression_status
from app.services.filtering import get_allowed_consequences
from app.services.evidence import lookup as lookup_evidence
from app.services.hla_service import HLA_AVAILABLE, hla_status
from app.services.qc import PASS
from app.services.self_filter import is_self_similar
from app.services.somatic import SHARED

_PROTEIN_CHANGE_RE = re.compile(r"^p\.([A-Z*?])(\d+)([A-Z*?])$")

_STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")


def _sanitize_peptide(sequence: str | None) -> str | None:
    """Return a standard Class I peptide (8-11 aa, no non-standard residues)."""
    if not sequence:
        return None
    cleaned = "".join(ch for ch in sequence.upper() if ch in _STANDARD_AA)
    if not cleaned:
        return None
    if len(cleaned) < 8:
        cleaned = (cleaned + "AAAAAAAAAA")[:9]
    elif len(cleaned) > 11:
        cleaned = cleaned[:11]
    return cleaned


class NeoantigenError(RuntimeError):
    pass


def _unique_valid_tumor_variants(db: Session, run_id: str) -> list[Variant]:
    statement = (
        select(Variant)
        .where(
            Variant.analysis_run_id == run_id,
            Variant.sample_role == "TUMOR",
            Variant.is_valid.is_(True),
            Variant.is_duplicate.is_(False),
        )
        .order_by(Variant.chromosome_normalized, Variant.position)
    )
    return list(db.execute(statement).scalars().all())


def _valid_hla(db: Session, run_id: str) -> list[HLAProfile]:
    statement = (
        select(HLAProfile)
        .where(
            HLAProfile.analysis_run_id == run_id,
            HLAProfile.is_valid.is_(True),
            HLAProfile.is_duplicate.is_(False),
        )
        .order_by(HLAProfile.allele_class, HLAProfile.allele)
    )
    return list(db.execute(statement).scalars().all())


def _expression_index(db: Session, run_id: str) -> tuple[dict, dict]:
    records = list(
        db.execute(
            select(ExpressionRecord).where(
                ExpressionRecord.analysis_run_id == run_id,
                ExpressionRecord.is_valid.is_(True),
            )
        )
        .scalars()
        .all()
    )
    by_symbol = {
        r.gene_symbol.upper(): r for r in records if r.gene_symbol
    }
    by_gene_id = {r.gene_id.upper(): r for r in records if r.gene_id}
    return by_symbol, by_gene_id


def _somatic_index(db: Session, run_id: str) -> dict:
    rows = list(
        db.execute(
            select(SomaticCandidate).where(SomaticCandidate.analysis_run_id == run_id)
        )
        .scalars()
        .all()
    )
    return {
        (r.chromosome, r.position, r.reference.upper(), r.alternate.upper()): r
        for r in rows
    }


def build_peptide(
    gene: str | None, protein_change: str | None, protein_position: int | None
) -> str | None:
    if not gene:
        return None
    transcript = next((t for t in MOCK_TRANSCRIPTS if t.gene == gene), None)
    if transcript is None:
        return None
    protein = "".join(
        translate(transcript.cds_sequence[i : i + 3])
        for i in range(0, len(transcript.cds_sequence) - 2, 3)
    )
    if not protein_position or protein_position < 1 or protein_position > len(protein):
        return _sanitize_peptide(protein)

    center = protein_position - 1
    start = max(0, center - 4)
    end = min(len(protein), center + 5)
    peptide = list(protein[start:end])
    match = _PROTEIN_CHANGE_RE.match(protein_change or "")
    if match:
        peptide[center - start] = match.group(3)
    return _sanitize_peptide("".join(peptide))


def _peptide_representation(gene, protein_change, peptide) -> str:
    return f"{gene or 'NA'}|{protein_change or 'NA'}|{peptide or 'NA'}"


def _ensure_ready(db: Session, run: AnalysisRun) -> None:
    if run.status != PASS:
        raise NeoantigenError(f"Analysis run is {run.status}; a PASS run is required.")
    try:
        require_traceable_annotations(db, run)
    except AnnotationGateError as exc:
        raise NeoantigenError(str(exc)) from exc
    hla = hla_status(db, run)
    if hla["status"] != HLA_AVAILABLE:
        raise NeoantigenError(f"HLA status is {hla['status']}: {hla['message']}")
    expression = expression_status(db, run)
    if expression["status"] != EXPRESSION_AVAILABLE:
        raise NeoantigenError(
            f"Expression status is {expression['status']}: {expression['message']}"
        )


def generate_candidates(db: Session, run: AnalysisRun) -> list[NeoantigenCandidate]:
    _ensure_ready(db, run)

    _, annotations = require_traceable_annotations(db, run)
    allowed = set(get_allowed_consequences(db, run.project_id))

    db.execute(
        delete(NeoantigenCandidate).where(
            NeoantigenCandidate.analysis_run_id == run.id
        )
    )
    db.commit()

    hla = _valid_hla(db, run.id)
    by_symbol, by_gene_id = _expression_index(db, run.id)
    somatic = _somatic_index(db, run.id)

    created: list[NeoantigenCandidate] = []
    for variant in _unique_valid_tumor_variants(db, run.id):
        annotation = annotations.get(variant.id)
        if annotation is None or annotation.status in (
            AnnotationStatus.FAILED.value,
            AnnotationStatus.UNAVAILABLE.value,
        ):
            continue

        gene = annotation.gene
        expression_record = None
        if gene and gene.upper() in by_symbol:
            expression_record = by_symbol[gene.upper()]
        elif annotation.gene_id and annotation.gene_id.upper() in by_gene_id:
            expression_record = by_gene_id[annotation.gene_id.upper()]

        classification = somatic.get(
            (
                variant.chromosome_normalized or variant.chromosome or "",
                variant.position or 0,
                (variant.reference or "").upper(),
                (variant.alternate or "").upper(),
            )
        )

        expression_evidence = {
            "matched": expression_record is not None,
            "gene_symbol": gene,
            "expression_value": expression_record.expression_value
            if expression_record
            else None,
            "unit": expression_record.unit if expression_record else None,
            "source": expression_record.source if expression_record else None,
            "status": EXPRESSION_AVAILABLE if expression_record else "NOT_FOUND",
        }
        mutation_evidence = {
            "classification": classification.classification if classification else None,
            "tumor_allele_frequency": variant.allele_frequency,
            "normal_allele_frequency": classification.normal_allele_frequency
            if classification
            else None,
            "tumor_depth": variant.depth,
            "normal_depth": classification.normal_depth if classification else None,
            "quality": variant.quality,
            "filter": variant.filter,
            "variant_type": variant.variant_type,
        }

        # Real providers supply the mutant peptide from the reference protein;
        # the mock provider falls back to the mock transcript builder.
        peptide = annotation.mutated_peptide or build_peptide(
            gene, annotation.protein_change, annotation.protein_position
        )
        representation = _peptide_representation(gene, annotation.protein_change, peptide)

        # Self-protein off-target safety filter (only when a proteome is configured).
        self_similar = is_self_similar(peptide) if peptide else False
        if self_similar:
            mutation_evidence["self_similar"] = True

        is_germline = bool(
            classification and classification.classification == SHARED
        )
        if peptide is None:
            mutation_evidence["reject_reason"] = "NO_MUTANT_PEPTIDE"
        if is_germline:
            mutation_evidence["reject_reason"] = "GERMLINE_SHARED"

        if is_germline:
            # Present in the normal sample (germline/polymorphism) — never a
            # tumour-specific neoantigen candidate.
            status = CANDIDATE_REJECTED
        elif self_similar:
            status = CANDIDATE_REJECTED
        elif peptide is None:
            # A neoantigen candidate is meaningless without a mutant peptide
            # (e.g. a stop-gained variant, or a terminal residue with no window).
            status = CANDIDATE_REJECTED
        elif annotation.consequence in allowed:
            status = CANDIDATE_GENERATED
        else:
            status = CANDIDATE_REJECTED

        for profile in hla:
            ms_evidence = lookup_evidence(peptide, profile.allele)
            candidate_evidence = {**mutation_evidence, "ms_evidence": ms_evidence}
            candidate = NeoantigenCandidate(
                analysis_run_id=run.id,
                variant_id=variant.id,
                somatic_candidate_id=classification.id if classification else None,
                hla_profile_id=profile.id,
                gene=gene,
                gene_id=annotation.gene_id,
                transcript=annotation.transcript,
                transcript_id=annotation.transcript_id,
                protein_change=annotation.protein_change,
                consequence=annotation.consequence,
                impact=annotation.impact,
                peptide_representation=representation,
                peptide_sequence=peptide,
                hla_allele=profile.allele,
                hla_class=profile.allele_class,
                expression_evidence=expression_evidence,
                mutation_evidence=candidate_evidence,
                prediction_status=PREDICTION_PENDING,
                status=status,
            )
            db.add(candidate)
            created.append(candidate)

    db.commit()
    for candidate in created:
        db.refresh(candidate)
    return created


def predict_candidates(db: Session, run: AnalysisRun, provider_name: str) -> dict:
    try:
        provider = get_prediction_provider(provider_name)
    except UnknownPredictionProviderError as exc:
        raise NeoantigenError(str(exc)) from exc

    provider_status = provider.health_check()
    candidates = list(
        db.execute(
            select(NeoantigenCandidate).where(
                NeoantigenCandidate.analysis_run_id == run.id,
                NeoantigenCandidate.status != CANDIDATE_REJECTED,
            )
        )
        .scalars()
        .all()
    )

    if provider_status != ProviderStatus.MOCK and provider_status != ProviderStatus.AVAILABLE:
        # Never substitute the mock provider for a real/unavailable one.
        db.execute(
            delete(PredictionResult).where(PredictionResult.analysis_run_id == run.id)
        )
        for candidate in candidates:
            candidate.prediction_status = provider_status.value
            candidate.status = CANDIDATE_GENERATED
            candidate.ranking_score = None
            candidate.ranking_evidence = None
            candidate.error_message = (
                f"Prediction provider '{provider_name}' is {provider_status.value}. "
                "PREDICTION UNAVAILABLE — mock results are not substituted."
            )
        db.commit()
        return {
            "provider": provider_name,
            "provider_status": provider_status.value,
            "is_mock": provider.is_mock,
            "predicted": 0,
            "unavailable": len(candidates),
        }

    predictable: list[NeoantigenCandidate] = []
    for candidate in candidates:
        if candidate.peptide_sequence:
            predictable.append(candidate)
        else:
            candidate.prediction_status = PREDICTION_UNAVAILABLE
            candidate.ranking_score = None
            candidate.error_message = (
                "No mutant peptide could be derived for this variant; "
                "prediction skipped."
            )

    inputs = [
        PredictionInput(
            candidate_id=candidate.id,
            peptide=candidate.peptide_sequence,
            peptide_representation=candidate.peptide_representation,
            hla_allele=candidate.hla_allele or "",
            gene=candidate.gene,
            protein_change=candidate.protein_change,
            mutation_offset=(len(candidate.peptide_sequence) // 2)
            if candidate.peptide_sequence
            else None,
        )
        for candidate in predictable
    ]
    validation = provider.validate_input(inputs)
    if not validation.ok:
        raise NeoantigenError(validation.reason or "Invalid prediction input")

    try:
        outputs = provider.predict(inputs)
    except Exception as exc:  # noqa: BLE001 - provider failure is never masked
        raise NeoantigenError(
            f"Prediction provider '{provider_name}' failed: {exc}"
        ) from exc

    by_candidate = {output.candidate_id: output for output in outputs}
    now = datetime.now(timezone.utc)
    prediction_status = PREDICTION_MOCK if provider.is_mock else provider_status.value

    # Write transaction starts here (after the slow provider call): replace
    # prior predictions and persist the new results in one short commit.
    db.execute(
        delete(PredictionResult).where(PredictionResult.analysis_run_id == run.id)
    )

    for candidate in candidates:
        output = by_candidate.get(candidate.id)
        if output is None:
            candidate.prediction_status = PREDICTION_UNAVAILABLE
            candidate.ranking_score = None
            candidate.error_message = (
                "PREDICTION UNAVAILABLE — provider did not produce a result for "
                "this HLA/peptide (e.g. Class II or unsupported input). Mock is not "
                "substituted."
            )
            continue
        candidate.prediction_status = prediction_status
        candidate.status = (
            CANDIDATE_PREDICTED if output.prediction_value is not None else CANDIDATE_UNCERTAIN
        )
        candidate.error_message = None
        db.add(
            PredictionResult(
                candidate_id=candidate.id,
                analysis_run_id=run.id,
                hla=output.hla,
                prediction_value=output.prediction_value,
                metric_name=output.metric_name,
                provider=output.provider,
                provider_version=output.provider_version,
                status=output.status,
                input_hash=output.input_hash,
                detail=output.detail,
                timestamp=now,
            )
        )

    db.commit()
    return {
        "provider": provider_name,
        "provider_status": provider_status.value,
        "is_mock": provider.is_mock,
        "predicted": len(outputs),
        "unavailable": len(candidates) - len(outputs),
    }


def get_or_create_ranking_config(
    db: Session, project_id: str
) -> RankingConfiguration:
    config = (
        db.execute(
            select(RankingConfiguration).where(
                RankingConfiguration.project_id == project_id
            )
        )
        .scalars()
        .first()
    )
    if config is None:
        config = RankingConfiguration(
            project_id=project_id,
            name="default",
            weights=dict(DEFAULT_WEIGHTS),
            version="1.0.0",
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


_HIGHER_IS_BETTER = {"mhcflurry", "mhcnuggets", "panel", "consensus", "mock"}


def _wildtype_peptide(peptide: str | None, protein_change: str | None) -> str | None:
    """Reconstruct the wild-type peptide by restoring the reference residue."""
    if not peptide:
        return None
    match = _PROTEIN_CHANGE_RE.match(protein_change or "")
    if not match:
        return None
    ref_aa = match.group(1)
    if ref_aa in ("*", "?"):
        return None
    offset = len(peptide) // 2
    if offset >= len(peptide):
        return None
    residues = list(peptide)
    if residues[offset] == ref_aa:
        return None  # not a substitution at the centre
    residues[offset] = ref_aa
    return "".join(residues)


def _compute_agretopicity(
    db: Session,
    run: AnalysisRun,
    candidates: list[NeoantigenCandidate],
    latest_prediction: dict[str, float | None],
) -> dict[str, float]:
    """(mutant − wild-type) predicted binding advantage, per candidate.

    Uses the run's own prediction provider to score the wild-type counterpart of
    each candidate peptide. Direction is normalised so that a larger value means
    the mutant is presented better than the self peptide. Returns {} when no
    real provider is available (agretopicity is then simply not scored).
    """
    row = db.execute(
        select(PredictionResult.provider)
        .where(
            PredictionResult.analysis_run_id == run.id,
            PredictionResult.status.in_([PREDICTION_MOCK, "AVAILABLE"]),
        )
        .limit(1)
    ).first()
    provider_name = row[0] if row and row[0] else None
    if not provider_name:
        return {}
    provider = get_prediction_provider(provider_name)
    if provider.health_check() not in (ProviderStatus.MOCK, ProviderStatus.AVAILABLE):
        return {}
    higher_is_better = provider_name in _HIGHER_IS_BETTER

    inputs: list[PredictionInput] = []
    for candidate in candidates:
        wt = _wildtype_peptide(candidate.peptide_sequence, candidate.protein_change)
        if not wt:
            continue
        inputs.append(
            PredictionInput(
                candidate_id=candidate.id,
                peptide=wt,
                peptide_representation=candidate.peptide_representation or "",
                hla_allele=candidate.hla_allele or "",
                gene=candidate.gene,
                protein_change=candidate.protein_change,
                mutation_offset=len(wt) // 2,
            )
        )
    if not inputs:
        return {}
    outputs = provider.predict(inputs)
    wt_by_candidate = {
        out.candidate_id: out.prediction_value
        for out in outputs
        if out.prediction_value is not None
    }
    result: dict[str, float] = {}
    for candidate in candidates:
        mutant = latest_prediction.get(candidate.id)
        wt = wt_by_candidate.get(candidate.id)
        if mutant is None or wt is None:
            continue
        result[candidate.id] = (
            mutant - wt if higher_is_better else wt - mutant
        )
    return result


def rank_candidates(
    db: Session,
    run: AnalysisRun,
    weights: dict | None = None,
    config: RankingConfiguration | None = None,
) -> dict:
    if config is None:
        config = get_or_create_ranking_config(db, run.project_id)
    effective_weights = weights or config.weights or DEFAULT_WEIGHTS
    engine = CandidateRankingEngine(effective_weights)

    candidates = list(
        db.execute(
            select(NeoantigenCandidate).where(
                NeoantigenCandidate.analysis_run_id == run.id,
                NeoantigenCandidate.prediction_status.in_(
                    [PREDICTION_MOCK, "AVAILABLE"]
                ),
            )
        )
        .scalars()
        .all()
    )

    latest_prediction: dict[str, float | None] = {}
    for result in db.execute(
        select(PredictionResult).where(PredictionResult.analysis_run_id == run.id)
    ).scalars().all():
        latest_prediction[result.candidate_id] = result.prediction_value

    try:
        agretopicity = _compute_agretopicity(db, run, candidates, latest_prediction)
    except Exception:  # noqa: BLE001 - agretopicity is best-effort, never fatal
        agretopicity = {}

    for candidate in candidates:
        expression_value = None
        if candidate.expression_evidence:
            expression_value = candidate.expression_evidence.get("expression_value")
        mutation = None
        specificity = 0.0
        quality = None
        if candidate.mutation_evidence:
            mutation = candidate.mutation_evidence.get("tumor_allele_frequency")
            specificity = specificity_from_classification(
                candidate.mutation_evidence.get("classification")
            )
            quality = candidate.mutation_evidence.get("quality")

        result = engine.rank(
            RankingInput(
                presentation=latest_prediction.get(candidate.id),
                expression=expression_value,
                mutation=mutation,
                tumor_specificity=specificity,
                variant_quality=quality,
                ms_evidence=1.0
                if (candidate.mutation_evidence or {}).get("ms_evidence", {}).get("observed")
                else 0.0,
                clonality=mutation,
                agretopicity=agretopicity.get(candidate.id),
            )
        )
        candidate.ranking_score = result.score
        candidate.ranking_evidence = {
            "components": result.components,
            "weights": result.weights,
            "version": result.version,
            "disclaimer": DISCLAIMER,
        }
        candidate.ranking_configuration_id = config.id
        candidate.status = CANDIDATE_RANKED

    run.ranking_configuration_id = config.id
    run.ranking_config = {
        "id": config.id,
        "name": config.name,
        "weights": engine.weights,
        "version": engine.version,
    }
    db.commit()

    return {
        "ranking_configuration_id": config.id,
        "weights": engine.weights,
        "version": engine.version,
        "ranked": len(candidates),
        "disclaimer": DISCLAIMER,
    }


def run_neoantigen_engine(
    db: Session,
    run: AnalysisRun,
    provider_name: str,
    weights: dict | None = None,
) -> dict:
    generated = generate_candidates(db, run)
    prediction = predict_candidates(db, run, provider_name)
    config = get_or_create_ranking_config(db, run.project_id)
    ranking = rank_candidates(db, run, weights=weights, config=config)
    return {
        "generated": len(generated),
        "rejected": sum(1 for c in generated if c.status == CANDIDATE_REJECTED),
        "prediction": prediction,
        "ranking": ranking,
    }
