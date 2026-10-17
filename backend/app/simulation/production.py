"""Simulated production package for a research construct.

Every section is a *research simulation*. It is generated from mock/synthetic
data only and is explicitly **not for clinical or human use**. The output is a
simulated production operation file, not a validated manufacturing record.
"""
from __future__ import annotations

from datetime import datetime, timezone

MODULE_NAME = "mRNA Construct Research Simulation"
SIMULATION_DISCLAIMER = (
    "RESEARCH SIMULATION ONLY. Generated from mock/synthetic data. This is not a "
    "validated therapeutic design or manufacturing record and is NOT FOR CLINICAL "
    "OR HUMAN USE."
)


def _route_for(fmt: str) -> str:
    if fmt == "circRNA":
        return "intramuscular administration of circular RNA (simulated)"
    if fmt == "saRNA":
        return "intramuscular administration of self-amplifying RNA (simulated)"
    return f"{fmt} intramuscular administration (simulated)"


def _sop_steps(fmt: str) -> list[str]:
    steps = ["Linearise simulated DNA template (in silico step).",
             "In vitro transcription of the simulated construct."]
    if fmt == "circRNA":
        steps += [
            "Simulated PIE self-splicing → circularization of the transcript.",
            "Simulated RNase R digestion of residual linear RNA.",
        ]
    else:
        steps += ["5' capping and simulated tailing."]
    if fmt == "saRNA":
        steps += ["Simulated replicase cassette transcription check."]
    steps += [
        "Purification and simulated buffer exchange.",
        "Simulated encapsulation into lipid nanoparticles.",
    ]
    return steps


def build_production_package(construct, run, candidates: list) -> dict:
    count = len(candidates)
    fmt = construct.simulation_format
    generated_at = datetime.now(timezone.utc).isoformat()

    common = {
        "simulation": True,
        "not_for_clinical_use": True,
        "validated": False,
        "disclaimer": SIMULATION_DISCLAIMER,
    }

    manufacturing_parameters: dict = {
        "ivt_temperature_c": 37,
        "ivt_duration_minutes": 120,
        "construct_candidate_count": count,
    }
    release_criteria: dict = {
        "appearance": "Simulated: homogeneous suspension",
        "concentration_mg_ml": 0.5,
        "encapsulation_efficiency_min": 0.85,
        "identity": f"Matches simulated construct {construct.id[:8]}",
        "sterility": "Simulated result only",
    }
    if fmt == "circRNA":
        manufacturing_parameters["circularization_efficiency_target"] = 0.9
        release_criteria["circularization_purity_min"] = 0.90
        release_criteria["linear_residual"] = "Simulated ≤10% after RNase R digestion"
    else:
        manufacturing_parameters["target_capping_efficiency"] = 0.95
        manufacturing_parameters["target_encapsulation_efficiency"] = 0.9
    if fmt == "saRNA":
        manufacturing_parameters["full_length_replicon_target"] = 0.80
        release_criteria["full_length_replicon_min"] = 0.80

    package = {
        "module": MODULE_NAME,
        "simulation": True,
        "not_for_clinical_use": True,
        "validated": False,
        "disclaimer": SIMULATION_DISCLAIMER,
        "generated_at": generated_at,
        "construct_id": construct.id,
        "analysis_run_id": run.id,
        "simulation_format": fmt,
        "candidate_count": count,
        "construct_representation": construct.construct_representation,
        "sequence_length": len(construct.sequence or ""),
        "sections": {
            "human_dosing_regimen": {
                **common,
                "title": "Human Dosing Regimen (Simulation)",
                "route": _route_for(fmt),
                "prime": {"dose_micrograms": 100, "schedule_day": 0},
                "boost": {"dose_micrograms": 100, "schedule_day": 21},
                "note": "Simulated dose levels and schedule for research modelling only.",
            },
            "clinical_treatment_protocol": {
                **common,
                "title": "Clinical Treatment Protocol (Simulation)",
                "cohort_size": 12,
                "cycles": 2,
                "monitoring": "Simulated safety observation windows; not a real protocol.",
                "eligibility": "Synthetic research cohort definition.",
            },
            "laboratory_manufacturing_sop": {
                **common,
                "title": "Laboratory Manufacturing SOP (Simulation)",
                "steps": _sop_steps(fmt),
            },
            "manufacturing_parameters": {
                **common,
                "title": "Manufacturing Parameters (Simulation)",
                **manufacturing_parameters,
            },
            "release_criteria": {
                **common,
                "title": "Release Criteria (Simulation)",
                **release_criteria,
            },
            "actual_production_formulation": {
                **common,
                "title": "Production Formulation (Simulation)",
                "lipid_molar_ratios": {
                    "ionizable_lipid": 50,
                    "helper_lipid": 10,
                    "cholesterol": 38.5,
                    "peg_lipid": 1.5,
                },
                "buffer": "Simulated citrate buffer",
            },
            "production_instructions": {
                **common,
                "title": "Production Instructions (Simulation)",
                "operation_file": f"SIM-OP-{construct.id[:8].upper()}",
                "instructions": [
                    f"Load simulated construct {construct.id[:8]} ({fmt}).",
                    f"Assemble {count} antigen segment(s) in the recorded order.",
                    "Run simulated IVT per manufacturing_parameters.",
                    "Perform simulated purification and encapsulation.",
                    "Record simulated in-process checks per release_criteria.",
                ],
            },
        },
    }
    return package
