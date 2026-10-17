"""Production blueprint package derived from the designed sequence.

Every field here is derived from the construct's sequence and its sequence-QC —
not hardcoded clinical content. Research use only.
"""
from __future__ import annotations

from app.blueprint.design import DesignedConstruct
from app.blueprint.sequence_qc import SequenceQc

DISCLAIMER = (
    "RESEARCH USE ONLY. In-silico design; not experimentally validated and NOT "
    "for clinical or human use. Manufacturing parameters are templates."
)

T7_PROMOTER = "TAATACGACTCACTATAG"

_COMPLEMENT = str.maketrans("ACGT", "TGCA")


def _revcomp(seq: str) -> str:
    return seq.translate(_COMPLEMENT)[::-1]


def build_sequence_design(designed: DesignedConstruct) -> dict:
    return {
        "format": designed.format_key,
        "circular": designed.circular,
        "dna_length": len(designed.dna),
        "rna_length": len(designed.rna),
        "gc_percent": designed.gc_percent,
        "cai": designed.cai,
        "tai": designed.tai,
        "expression_score": designed.expression_score,
        "stability_score": designed.stability_score,
        "u_content": designed.u_content,
        "innate_immune_score": designed.innate_immune_score,
        "innate_immune": designed.innate_immune,
        "three_utr_selection": designed.three_utr_selection,
        "codon_stability": designed.codon_stability,
        "codon_pair_score": designed.codon_pair_score,
        "codon_metrics_model": designed.codon_metrics_model,
        "ivt_start": designed.ivt_start,
        "poly_a_design": designed.poly_a_design,
        "mfe_per_nt": designed.mfe_per_nt,
        "ligation_junction": designed.ligation_junction,
        "utr_selection": designed.utr_selection,
        "regions": [
            {
                "name": r.name,
                "type": r.type,
                "start": r.start,
                "end": r.end,
                "length": r.end - r.start,
            }
            for r in designed.regions
        ],
    }


def build_manufacturing(designed: DesignedConstruct) -> dict:
    dna = designed.dna
    forward = T7_PROMOTER + dna[:20]
    reverse = _revcomp(dna[-25:])
    cloning_note = "linear IVT template (no plasmid) or restriction sites chosen per vector"
    if designed.circular:
        cloning_note += (
            "; circularization via PIE self-splicing from the linear precursor (simulated)"
        )
    elif designed.format_key == "saRNA":
        cloning_note += "; self-amplifying replicon (replicase cassette simulated)"
    return {
        "ivt_template": {
            "t7_promoter": T7_PROMOTER,
            "template_sequence": T7_PROMOTER + dna,
            "transcription_unit_length": len(T7_PROMOTER) + len(dna),
        },
        "primers": {
            "forward": forward,
            "reverse": reverse,
            "forward_tm_note": "Contains T7 promoter",
        },
        "cloning": {
            "strategy": cloning_note,
            "screened_restriction_sites_removed": True,
        },
        "lnp_formulation": {
            "ionizable_lipid": 50,
            "helper_lipid": 10,
            "cholesterol": 38.5,
            "peg_lipid": 1.5,
            "n_p_ratio": 6,
            "note": "Template parameters; confirm per laboratory system (simulation).",
        },
    }


def build_release_criteria(designed: DesignedConstruct, qc: SequenceQc) -> dict:
    metrics = qc.metrics
    criteria = {
        "sequence_identity": "Consistent with blueprint sequence (input hash check)",
        "gc_percent": f"{metrics['gc_percent']}% (target 40-60%)",
        "length_nt": metrics["length"],
        "integrity": "Denaturing gel / CE single band (to be confirmed experimentally)",
        "encapsulation_efficiency_min": 0.85,
        "sterility_endotoxin": "Per laboratory standards (to be confirmed)",
        "note": "Release criteria are templates and require laboratory validation and confirmation.",
    }
    if designed.circular:
        criteria["circularization_purity_min"] = 0.90
        criteria["linear_residual_max"] = "≤10% after RNase R digestion (to be confirmed)"
        criteria["note"] += " Circular RNA: junction PCR / RNase R resistance replaces cap and poly(A) criteria."
    elif designed.format_key == "saRNA":
        criteria["capping_efficiency_min"] = 0.95
        criteria["poly_a_length_min_nt"] = 100
        criteria["full_length_replicon_min"] = 0.80
        criteria["note"] += " saRNA: full-length replicon integrity (replicase retained) is an additional release gate."
    else:
        criteria["capping_efficiency_min"] = 0.95
        criteria["poly_a_length_min_nt"] = 100
    return criteria


def build_mrna_chemistry(designed: DesignedConstruct) -> dict:
    poly_a = next((r.end - r.start for r in designed.regions if r.type == "POLY_A"), 0)
    base = {
        "modified_nucleotides": "N1-methylpseudouridine (m1Ψ) / 5-methylcytidine (m5C) (template; per laboratory system)",
        "poly_a_length_nt": poly_a,
        "note": "Template parameters requiring experimental confirmation; nucleoside modification / capping / purification per laboratory SOP.",
    }
    if designed.circular:
        return {
            **base,
            "cap": None,
            "translation_initiation": "IRES-driven (simulated IRES placeholder)",
            "circularization": "Permuted intron-exon (PIE) self-splicing (simulated arms)",
            "template_type": "Linear IVT precursor → circularized RNA (simulated)",
            "note": "Circular RNA: no cap and no poly(A) tail; RNase R linear-residual digestion assumed in the simulated SOP.",
        }
    if designed.format_key == "saRNA":
        return {
            **base,
            "cap": "Cap1 (m7G + 2'-O-methylation)",
            "replicase": "Simulated alphavirus replicase cassette placeholder (not functional)",
            "subgenomic_promoter": "26S subgenomic promoter (simulated, Kozak-context ending)",
            "template_type": "Linear IVT (T7 promoter), self-amplifying replicon",
        }
    return {
        **base,
        "cap": "Cap1 (m7G + 2'-O-methylation)",
        "template_type": "Linear IVT (T7 promoter)",
    }


def augment_package(
    package: dict, designed: DesignedConstruct, qc: SequenceQc
) -> dict:
    """Add sequence-derived sections into an existing production package."""
    package = dict(package)
    package["disclaimer"] = DISCLAIMER
    package["sequence_design"] = build_sequence_design(designed)
    package["sequence_qc"] = qc.as_dict()
    package["manufacturing"] = build_manufacturing(designed)
    package["mrna_chemistry"] = build_mrna_chemistry(designed)
    package["release_criteria_derived"] = build_release_criteria(designed, qc)
    package["production_ready"] = qc.status == "PRODUCTION_READY"
    return package
