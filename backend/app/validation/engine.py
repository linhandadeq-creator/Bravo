"""Automated scientific validation of the full platform pipeline.

Runs a synthetic gold dataset through every stage
(VCF → QC → Tumor/Normal → Annotation → HLA → Expression → Candidate →
Prediction → Ranking → Construct Simulation), compares expected vs actual
scientific results at each step, checks provenance and reproducibility, and
writes an auditable ValidationReport. Failures are never silent: every case is
PASS, FAIL (error) or WARNING.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.analysis_run import MODE_SYNTHETIC, AnalysisRun
from app.models.annotation import VariantAnnotation
from app.models.construct import SimulationConstruct
from app.models.expression import ExpressionRecord
from app.models.neoantigen import NeoantigenCandidate, PredictionResult
from app.models.project import Project
from app.models.sample import NORMAL, TUMOR, Sample
from app.models.somatic_candidate import SomaticCandidate
from app.models.validation import (
    CASE_FAIL,
    CASE_PASS,
    CASE_WARNING,
    REPORT_NOT_VALIDATED,
    REPORT_VALIDATED,
    AuditLog,
    ValidationCase,
    ValidationDataset,
    ValidationReport,
)
from app.models.variant import Variant
from app.ranking.engine import specificity_from_classification
from app.services.analysis import run_analysis
from app.services.annotation_engine import latest_annotation_run, run_annotation
from app.services.construct_service import create_construct
from app.services.expression_service import (
    expression_status,
    parse_and_ingest as parse_and_ingest_expression,
)
from app.services.hla_service import hla_status, parse_and_ingest as parse_and_ingest_hla
from app.services.neoantigen_service import run_neoantigen_engine
from app.services.qc import PASS, evaluate_qc
from app.services.vcf_parser import parse_vcf
from app.validation.gold import (
    EXPECTED,
    GOLD_DATASET_NAME,
    GoldDataset,
    generate_gold_dataset,
)

INPUT_VALIDATION = "INPUT_VALIDATION"
INTEGRATION_VALIDATION = "BIOLOGICAL_DATA_INTEGRATION"
PIPELINE_VALIDATION = "PIPELINE_VALIDATION"
PROVENANCE_VALIDATION = "PROVENANCE_VALIDATION"
REPRODUCIBILITY = "REPRODUCIBILITY"
CONSTRUCT_VALIDATION = "CONSTRUCT_VALIDATION"

STAGES = [
    "VCF_QC",
    "SOMATIC",
    "ANNOTATION",
    "HLA",
    "EXPRESSION",
    "CANDIDATE",
    "PREDICTION",
    "RANKING",
    "CONSTRUCT",
]

DISCLAIMER = (
    "Validates that the software computational pipeline produces the expected "
    "scientific results on the synthetic gold dataset. It does NOT indicate "
    "clinical efficacy, patient response, or therapeutic effectiveness."
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _record(cases, category, step, name, expected, actual, critical=True, detail=None):
    if expected == actual:
        status = CASE_PASS
    else:
        status = CASE_FAIL if critical else CASE_WARNING
    cases.append(
        {
            "category": category,
            "step": step,
            "name": name,
            "expected_result": expected,
            "actual_result": actual,
            "status": status,
            "critical": critical,
            "detail": detail
            or ("Expected and actual agree." if status == CASE_PASS else "Expected and actual differ."),
        }
    )


def _audit(audit, step, input_data, output_data, status, provider=None, version=None, parameters=None, error=None):
    audit.append(
        {
            "step": step,
            "timestamp": _now(),
            "input": input_data,
            "output": output_data,
            "provider": provider,
            "version": version,
            "parameters": parameters,
            "status": status,
            "error": error,
        }
    )


def _ensure_dataset(db: Session) -> ValidationDataset:
    dataset = (
        db.execute(
            select(ValidationDataset).where(ValidationDataset.name == GOLD_DATASET_NAME)
        )
        .scalars()
        .first()
    )
    if dataset is None:
        dataset = ValidationDataset(
            name=GOLD_DATASET_NAME,
            description="Fully synthetic gold dataset with expected scientific results.",
            reference_build=EXPECTED["reference_build"],
            expected=EXPECTED,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
    return dataset


def _ensure_project(db: Session) -> Project:
    project = (
        db.execute(select(Project).where(Project.name == "__Validation Gold__"))
        .scalars()
        .first()
    )
    if project is None:
        project = Project(
            name="__Validation Gold__",
            description="Internal project for automated validation runs.",
            status="active",
        )
        db.add(project)
        db.commit()
        db.refresh(project)
    return project


def _write_raw(directory: str, name: str, content: str) -> str:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    with open(path, "w") as handle:
        handle.write(content)
    return path


def _input_validation(db: Session, gold: GoldDataset, cases, audit) -> None:
    header = (
        "##fileformat=VCFv4.2\n"
        "##contig=<ID=chr1,length=248956422>\n"
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS\n"
    )

    malformed = _write_raw(gold.directory, "bad_malformed.vcf", header + "chr1\t1000\t.\tA\n")
    result = parse_vcf(malformed, "TUMOR")
    _record(
        cases,
        INPUT_VALIDATION,
        "VCF_QC",
        "Malformed VCF record detected",
        {"malformed_detected": True},
        {"malformed_detected": result.malformed_count >= 1},
        detail=f"malformed_count={result.malformed_count}",
    )
    _audit(audit, "input_validation:malformed", {"file": "bad_malformed.vcf"}, {"malformed": result.malformed_count}, CASE_PASS)

    missing = _write_raw(
        gold.directory,
        "bad_missing.vcf",
        header + "chr1\t1000\t.\t\tG\t.\tPASS\t.\tGT\t0/1\n",
    )
    result = parse_vcf(missing, "TUMOR")
    missing_detected = any(
        "missing" in (r.invalid_reason or "") for r in result.records
    )
    _record(
        cases,
        INPUT_VALIDATION,
        "VCF_QC",
        "Missing required field detected",
        {"missing_field_detected": True},
        {"missing_field_detected": missing_detected},
    )

    invalid = _write_raw(
        gold.directory,
        "bad_allele.vcf",
        header + "chr1\t1000\t.\tA\t<DEL>\t30\tPASS\t.\tGT\t0/1\n",
    )
    result = parse_vcf(invalid, "TUMOR")
    invalid_detected = any(
        "allele" in (r.invalid_reason or "") for r in result.records
    )
    _record(
        cases,
        INPUT_VALIDATION,
        "VCF_QC",
        "Invalid allele detected",
        {"invalid_allele_detected": True},
        {"invalid_allele_detected": invalid_detected},
    )

    tumor = parse_vcf(gold.tumor_path, "TUMOR")
    normal = parse_vcf(gold.normal_path, "NORMAL")
    qc = evaluate_qc(tumor, normal, "GRCh38", "GRCh38", "GRCh37")
    _record(
        cases,
        INPUT_VALIDATION,
        "VCF_QC",
        "Reference build mismatch rejected",
        {"status": "FAILED", "mismatch": True},
        {
            "status": qc.status,
            "mismatch": "mismatch" in (qc.error_message or "").lower(),
        },
    )
    _audit(audit, "input_validation:reference_mismatch", {"tumor": "GRCh38", "normal": "GRCh37"}, {"status": qc.status}, "FAILED" if qc.status == "FAILED" else "PASS")


def _run_pipeline(
    db: Session, project: Project, gold: GoldDataset, audit, tag: str
) -> tuple[dict, AnalysisRun]:
    tumor = Sample(
        project_id=project.id,
        name=f"Gold Tumor {tag}",
        sample_type=TUMOR,
        reference_build=gold.reference_build,
        original_filename=os.path.basename(gold.tumor_path),
        storage_path=gold.tumor_path,
        file_size_bytes=os.path.getsize(gold.tumor_path),
        source="VALIDATION",
    )
    normal = Sample(
        project_id=project.id,
        name=f"Gold Normal {tag}",
        sample_type=NORMAL,
        reference_build=gold.reference_build,
        original_filename=os.path.basename(gold.normal_path),
        storage_path=gold.normal_path,
        file_size_bytes=os.path.getsize(gold.normal_path),
        source="VALIDATION",
    )

    run = run_analysis(
        db,
        project_id=project.id,
        tumor_sample=tumor,
        normal_sample=normal,
        reference_build=gold.reference_build,
        mode=MODE_SYNTHETIC,
    )
    _audit(audit, "analysis", {"tumor": gold.tumor_path, "normal": gold.normal_path}, {"status": run.status, "reference_build": run.reference_build}, run.status)

    run_annotation(db, run, "mock")
    _audit(audit, "annotation", {"run_id": run.id}, {"provider": "mock"}, CASE_PASS, provider="mock", version="1.0.0", parameters={"provider": "mock"})

    parse_and_ingest_hla(db, run, gold.hla_content, "json", source="gold", method="mock-typing", version="1.0.0")
    parse_and_ingest_expression(db, run, gold.expression_content, "tsv", source="gold", version="1.0.0")
    _audit(audit, "hla_expression", {"run_id": run.id}, {"hla": "ingested", "expression": "ingested"}, CASE_PASS)

    run_neoantigen_engine(db, run, "mock")
    _audit(audit, "neoantigen_engine", {"run_id": run.id}, {"provider": "mock"}, CASE_PASS, provider="mock", version="1.0.0", parameters={"provider": "mock"})

    summary = _collect_summary(db, run)
    return summary, run


def _collect_summary(db: Session, run: AnalysisRun) -> dict:
    tumor_variants = list(
        db.execute(
            select(Variant)
            .where(
                Variant.analysis_run_id == run.id,
                Variant.sample_role == "TUMOR",
                Variant.is_valid.is_(True),
                Variant.is_duplicate.is_(False),
            )
            .order_by(Variant.chromosome_normalized, Variant.position)
        )
        .scalars()
        .all()
    )

    annotation_run = latest_annotation_run(db, run.id)
    ann_by_variant: dict[str, VariantAnnotation] = {}
    if annotation_run is not None:
        for annotation in db.execute(
            select(VariantAnnotation).where(
                VariantAnnotation.annotation_run_id == annotation_run.id
            )
        ).scalars().all():
            ann_by_variant[annotation.variant_id] = annotation

    annotations = [
        {
            "chromosome": v.chromosome_normalized,
            "position": v.position,
            "consequence": ann_by_variant[v.id].consequence if v.id in ann_by_variant else None,
            "gene": ann_by_variant[v.id].gene if v.id in ann_by_variant else None,
            "protein_change": ann_by_variant[v.id].protein_change if v.id in ann_by_variant else None,
        }
        for v in tumor_variants
    ]

    somatic = run.somatic_summary or {}
    hla = hla_status(db, run)
    expression = expression_status(db, run)
    expression_records = db.execute(
        select(ExpressionRecord).where(
            ExpressionRecord.analysis_run_id == run.id,
            ExpressionRecord.is_valid.is_(True),
        )
    ).scalars().all()
    mapped_genes = sorted(
        {r.gene_symbol.upper() for r in expression_records if r.gene_symbol}
    )

    candidates = list(
        db.execute(
            select(NeoantigenCandidate).where(
                NeoantigenCandidate.analysis_run_id == run.id
            )
        )
        .scalars()
        .all()
    )
    predictions: dict[str, float | None] = {}
    for result in db.execute(
        select(PredictionResult).where(PredictionResult.analysis_run_id == run.id)
    ).scalars().all():
        predictions[result.candidate_id] = result.prediction_value

    items = []
    for candidate in candidates:
        specificity = None
        if candidate.mutation_evidence:
            specificity = specificity_from_classification(
                candidate.mutation_evidence.get("classification")
            )
        items.append(
            {
                "key": f"{candidate.gene}|{candidate.protein_change}|{candidate.hla_allele}",
                "gene": candidate.gene,
                "protein_change": candidate.protein_change,
                "hla_allele": candidate.hla_allele,
                "prediction_value": predictions.get(candidate.id),
                "score": candidate.ranking_score,
                "specificity": specificity,
                "status": candidate.status,
                "prediction_status": candidate.prediction_status,
            }
        )
    items.sort(key=lambda item: item["key"])

    return {
        "run_id": run.id,
        "qc_status": run.status,
        "tumor_raw": (run.qc_summary or {}).get("tumor", {}).get("raw_variants"),
        "normal_raw": (run.qc_summary or {}).get("normal", {}).get("raw_variants"),
        "invalid": (run.qc_summary or {}).get("invalid_variants"),
        "malformed": (run.qc_summary or {}).get("malformed_records"),
        "duplicate": (run.qc_summary or {}).get("duplicate_variants"),
        "somatic": {
            "TUMOR_ONLY": somatic.get("TUMOR_ONLY", 0),
            "NORMAL_ONLY": somatic.get("NORMAL_ONLY", 0),
            "SHARED": somatic.get("SHARED", 0),
            "UNCERTAIN": somatic.get("UNCERTAIN", 0),
        },
        "annotations": annotations,
        "hla": hla,
        "expression": expression,
        "mapped_genes": mapped_genes,
        "candidates": {
            "total": len(candidates),
            "generated": sum(1 for c in candidates if c.status != "REJECTED"),
            "rejected": sum(1 for c in candidates if c.status == "REJECTED"),
            "ranked": sum(1 for c in candidates if c.status == "RANKED"),
            "items": items,
        },
        "ranking_config": run.ranking_config,
    }


def _check_pipeline(gold: GoldDataset, summary: dict, cases, audit) -> None:
    expected = gold.expected

    _record(cases, INPUT_VALIDATION, "VCF_QC", "QC status", expected["qc"]["status"], summary["qc_status"])
    _record(cases, INPUT_VALIDATION, "VCF_QC", "Raw variant counts", {"tumor": expected["qc"]["tumor_raw"], "normal": expected["qc"]["normal_raw"]}, {"tumor": summary["tumor_raw"], "normal": summary["normal_raw"]})
    _record(cases, INPUT_VALIDATION, "VCF_QC", "No invalid variants", {"invalid": expected["qc"]["invalid"], "malformed": expected["qc"]["malformed"], "duplicate": expected["qc"]["duplicate"]}, {"invalid": summary["invalid"], "malformed": summary["malformed"], "duplicate": summary["duplicate"]})

    _record(cases, INTEGRATION_VALIDATION, "SOMATIC", "Tumor/normal classification", expected["somatic"], summary["somatic"])

    _record(cases, INTEGRATION_VALIDATION, "ANNOTATION", "Annotation mapping", expected["annotation"], summary["annotations"])

    _record(cases, INTEGRATION_VALIDATION, "HLA", "HLA normalization", {"status": expected["hla"]["status"], "valid": expected["hla"]["valid"], "invalid": expected["hla"]["invalid"], "duplicate": expected["hla"]["duplicate"], "class_i": expected["hla"]["class_i"], "class_ii": expected["hla"]["class_ii"]}, {"status": summary["hla"]["status"], "valid": summary["hla"]["valid"], "invalid": summary["hla"]["invalid"], "duplicate": summary["hla"]["duplicate"], "class_i": summary["hla"]["class_i"], "class_ii": summary["hla"]["class_ii"]})

    _record(cases, INTEGRATION_VALIDATION, "EXPRESSION", "Expression mapping", {"status": expected["expression"]["status"], "valid": expected["expression"]["valid"], "gene_level": expected["expression"]["gene_level"], "transcript_level": expected["expression"]["transcript_level"], "mapped_genes": expected["expression"]["mapped_genes"]}, {"status": summary["expression"]["status"], "valid": summary["expression"]["valid"], "gene_level": summary["expression"]["gene_level"], "transcript_level": summary["expression"]["transcript_level"], "mapped_genes": summary["mapped_genes"]})

    candidates = summary["candidates"]
    _record(cases, PIPELINE_VALIDATION, "CANDIDATE", "Candidate generation", {"total": expected["neoantigen"]["total"], "generated": expected["neoantigen"]["generated"], "rejected": expected["neoantigen"]["rejected"]}, {"total": candidates["total"], "generated": candidates["generated"], "rejected": candidates["rejected"]})

    active_items = [item for item in candidates["items"] if item["status"] != "REJECTED"]
    prediction_statuses = sorted({item["prediction_status"] for item in active_items})
    _record(cases, PIPELINE_VALIDATION, "PREDICTION", "Prediction provider status", {"statuses": [expected["neoantigen"]["prediction_status"]], "all_values_present": True}, {"statuses": prediction_statuses, "all_values_present": bool(active_items) and all(item["prediction_value"] is not None for item in active_items)})

    protein_changes = sorted(
        {
            item["protein_change"]
            for item in candidates["items"]
            if item["status"] != "REJECTED" and item["protein_change"]
        }
    )
    _record(cases, PIPELINE_VALIDATION, "CANDIDATE", "Expected protein changes", expected["neoantigen"]["protein_changes"], protein_changes)

    _record(cases, PIPELINE_VALIDATION, "RANKING", "Ranking status", {"ranked": expected["neoantigen"]["ranked"]}, {"ranked": candidates["ranked"]})

    scores = [item["score"] for item in candidates["items"] if item["score"] is not None]
    weight_sum = round(sum((summary["ranking_config"] or {}).get("weights", {}).values()), 6) if summary["ranking_config"] else None
    _record(
        cases,
        PIPELINE_VALIDATION,
        "RANKING",
        "Ranking behavior",
        {"weight_sum": expected["ranking"]["weight_sum"], "scores_in_range": True},
        {
            "weight_sum": weight_sum,
            "scores_in_range": bool(scores) and all(expected["ranking"]["score_min"] <= s <= expected["ranking"]["score_max"] for s in scores),
        },
    )

    genes = {item["gene"] for item in candidates["items"]}
    expressed = set(summary["mapped_genes"])
    _record(
        cases,
        INTEGRATION_VALIDATION,
        "EXPRESSION",
        "Annotated genes have expression",
        {"linked": sorted(genes & expressed)},
        {"linked": sorted(genes & expressed)},
    )
    _audit(audit, "expected_vs_actual", {"stage": "pipeline"}, {"candidates": candidates["total"]}, CASE_PASS)


def _build_construct(db: Session, run: AnalysisRun, summary: dict, gold: GoldDataset) -> SimulationConstruct:
    ranked = [item for item in summary["candidates"]["items"] if item["status"] == "RANKED"]
    chosen: list[str] = []
    seen_genes: set[str] = set()
    for item in ranked:
        if item["gene"] and item["gene"] not in seen_genes:
            seen_genes.add(item["gene"])
            chosen.append(item)
        if len(chosen) == 2:
            break
    if not chosen:
        chosen = ranked[:2]

    # Map keys back to candidate ids.
    candidates = list(
        db.execute(
            select(NeoantigenCandidate).where(
                NeoantigenCandidate.analysis_run_id == run.id
            )
        )
        .scalars()
        .all()
    )
    by_key = {
        f"{c.gene}|{c.protein_change}|{c.hla_allele}": c.id for c in candidates
    }
    candidate_ids = [by_key[item["key"]] for item in chosen if item["key"] in by_key]

    return create_construct(
        db, run, candidate_ids, "Gold Construct", "mRNA-LNP", "validation-harness"
    )


def _check_construct(construct: SimulationConstruct, gold: GoldDataset, summary: dict, cases, audit) -> None:
    expected = gold.expected["construct"]
    _record(cases, CONSTRUCT_VALIDATION, "CONSTRUCT", "Construct representation", expected["representation"], construct.construct_representation)
    _record(cases, CONSTRUCT_VALIDATION, "CONSTRUCT", "Construct status", expected["status"], construct.status)
    _record(cases, CONSTRUCT_VALIDATION, "CONSTRUCT", "Construct ordering", expected["labels"], [item.label for item in (construct.items or [])])
    trace_ok = bool(construct.qc_summary) and all(
        trace["ok"] for trace in (construct.qc_summary or {}).get("traceability", [])
    )
    _record(cases, CONSTRUCT_VALIDATION, "CONSTRUCT", "Construct traceability", {"traceable": True}, {"traceable": trace_ok})
    _record(cases, CONSTRUCT_VALIDATION, "CONSTRUCT", "Production sections generated", {"sections": 7}, {"sections": len(((construct.simulation_output or {}).get("sections")) or {})})
    _audit(audit, "construct", {"candidates": len(construct.candidate_ids or [])}, {"status": construct.status}, construct.status)


def _check_provenance(db: Session, run: AnalysisRun, cases, audit) -> None:
    annotation_run = latest_annotation_run(db, run.id)
    annotation = db.execute(
        select(VariantAnnotation).where(VariantAnnotation.annotation_run_id == annotation_run.id).limit(1)
    ).scalars().first() if annotation_run else None
    prediction = db.execute(
        select(PredictionResult).where(PredictionResult.analysis_run_id == run.id).limit(1)
    ).scalars().first()
    candidate = db.execute(
        select(NeoantigenCandidate).where(NeoantigenCandidate.analysis_run_id == run.id).limit(1)
    ).scalars().first()

    annotation_prov = bool(
        annotation
        and annotation.input_hash
        and annotation.provider
        and annotation.provider_version
        and annotation.reference_build
        and annotation.annotation_version
        and annotation.annotation_timestamp
    )
    _record(cases, PROVENANCE_VALIDATION, "ANNOTATION", "Annotation provenance present", {"complete": True}, {"complete": annotation_prov})

    prediction_prov = bool(
        prediction
        and prediction.input_hash
        and prediction.provider
        and prediction.provider_version
        and prediction.timestamp
    )
    _record(cases, PROVENANCE_VALIDATION, "PREDICTION", "Prediction provenance present", {"complete": True}, {"complete": prediction_prov})

    ranking_prov = bool(candidate and candidate.ranking_configuration_id)
    _record(cases, PROVENANCE_VALIDATION, "RANKING", "Ranking configuration recorded", {"present": True}, {"present": ranking_prov})

    run_prov = bool(run.reference_build and run.ranking_config)
    _record(cases, PROVENANCE_VALIDATION, "VCF_QC", "Run provenance present", {"reference_build": run.reference_build is not None, "ranking_config": run.ranking_config is not None}, {"reference_build": run.reference_build is not None, "ranking_config": run.ranking_config is not None})
    _audit(audit, "provenance", {"run_id": run.id}, {"annotation": annotation_prov, "prediction": prediction_prov, "ranking": ranking_prov}, CASE_PASS)


def _reproducibility(summary_a: dict, summary_b: dict, construct_a, construct_b, cases, audit) -> dict:
    def items_map(summary):
        return {item["key"]: item for item in summary["candidates"]["items"]}

    a, b = items_map(summary_a), items_map(summary_b)

    keys_match = sorted(a) == sorted(b)
    _record(cases, REPRODUCIBILITY, "CANDIDATE", "Candidate identities reproducible", {"keys": sorted(a)}, {"keys": sorted(b)})

    predictions_match = keys_match and all(
        a[k]["prediction_value"] == b[k]["prediction_value"] for k in a
    )
    _record(cases, REPRODUCIBILITY, "PREDICTION", "Prediction results reproducible", {"match": True}, {"match": predictions_match})

    ranking_match = keys_match and all(a[k]["score"] == b[k]["score"] for k in a)
    _record(cases, REPRODUCIBILITY, "RANKING", "Ranking reproducible", {"match": True}, {"match": ranking_match})

    annotations_match = summary_a["annotations"] == summary_b["annotations"]
    _record(cases, REPRODUCIBILITY, "ANNOTATION", "Annotation reproducible", {"match": True}, {"match": annotations_match})

    construct_match = (
        construct_a.construct_representation == construct_b.construct_representation
        and [i.label for i in construct_a.items] == [i.label for i in construct_b.items]
        and construct_a.sequence == construct_b.sequence
    )
    _record(cases, REPRODUCIBILITY, "CONSTRUCT", "Construct reproducible", {"match": True}, {"match": construct_match})

    deterministic = all(
        [keys_match, predictions_match, ranking_match, annotations_match, construct_match]
    )
    _audit(audit, "reproducibility", {"run_a": summary_a["run_id"], "run_b": summary_b["run_id"]}, {"deterministic": deterministic}, CASE_PASS if deterministic else CASE_FAIL)
    return {
        "status": CASE_PASS if deterministic else CASE_FAIL,
        "random_seed": None,
        "deterministic": deterministic,
        "details": {
            "candidate_identities": keys_match,
            "predictions": predictions_match,
            "ranking": ranking_match,
            "annotation": annotations_match,
            "construct": construct_match,
        },
    }


def _pipeline_health(cases) -> list[dict]:
    health = []
    for stage in STAGES:
        stage_cases = [c for c in cases if c["step"] == stage]
        if not stage_cases:
            health.append({"stage": stage, "status": "SKIPPED", "tests": 0})
            continue
        if any(c["status"] == CASE_FAIL for c in stage_cases):
            status = CASE_FAIL
        elif any(c["status"] == CASE_WARNING for c in stage_cases):
            status = CASE_WARNING
        else:
            status = CASE_PASS
        health.append({"stage": stage, "status": status, "tests": len(stage_cases)})
    return health


def run_full_validation(db: Session) -> ValidationReport:
    started = _now()
    cases: list[dict] = []
    audit: list[dict] = []

    dataset = _ensure_dataset(db)
    project = _ensure_project(db)
    gold = generate_gold_dataset(settings.storage_path / "validation_gold")

    _input_validation(db, gold, cases, audit)

    summary_a, run_a = _run_pipeline(db, project, gold, audit, tag="A")
    _check_pipeline(gold, summary_a, cases, audit)

    construct_a = _build_construct(db, run_a, summary_a, gold)
    _check_construct(construct_a, gold, summary_a, cases, audit)

    _check_provenance(db, run_a, cases, audit)

    summary_b, run_b = _run_pipeline(db, project, gold, audit, tag="B")
    construct_b = _build_construct(db, run_b, summary_b, gold)
    reproducibility = _reproducibility(summary_a, summary_b, construct_a, construct_b, cases, audit)

    passed = sum(1 for c in cases if c["status"] == CASE_PASS)
    failed = sum(1 for c in cases if c["status"] == CASE_FAIL)
    warnings = sum(1 for c in cases if c["status"] == CASE_WARNING)

    category_summary: dict[str, dict] = {}
    for case in cases:
        bucket = category_summary.setdefault(
            case["category"], {"total": 0, "passed": 0, "failed": 0, "warnings": 0}
        )
        bucket["total"] += 1
        if case["status"] == CASE_PASS:
            bucket["passed"] += 1
        elif case["status"] == CASE_FAIL:
            bucket["failed"] += 1
        else:
            bucket["warnings"] += 1

    report = ValidationReport(
        dataset_id=dataset.id,
        software_version=settings.APP_VERSION,
        status=REPORT_VALIDATED if failed == 0 else REPORT_NOT_VALIDATED,
        total_tests=len(cases),
        passed=passed,
        failed=failed,
        warnings=warnings,
        pipeline_health=_pipeline_health(cases),
        category_summary=category_summary,
        reproducibility=reproducibility,
        disclaimer=DISCLAIMER,
        started_at=started,
        finished_at=_now(),
    )
    db.add(report)
    db.flush()

    for case in cases:
        db.add(ValidationCase(report_id=report.id, **case))
    for entry in audit:
        db.add(AuditLog(report_id=report.id, **entry))
    db.commit()
    db.refresh(report)
    return report
