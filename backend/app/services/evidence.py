"""MS / measured-ligand evidence.

Builds a local index of observed peptide–allele pairs from public immunopeptidome
data (the mass-spectrometry and binding measurements bundled with the MHCflurry
model, originally from IEDB-style sources). Used to flag candidates with direct
presentation evidence — a strong driver of experimental success rate.
"""
from __future__ import annotations

import bz2
import csv
import os
from pathlib import Path

from app.core.config import settings

_STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")
_cache: dict[tuple, tuple[set, set]] = {}


def _training_paths() -> list[str]:
    # An explicit source fully overrides the defaults (used for testing and
    # curated/custom evidence sets).
    explicit = (settings.EVIDENCE_MS_TRAINING or "").strip()
    if explicit:
        return [explicit] if os.path.isfile(explicit) else []

    paths: list[str] = []

    # Real MS ligands downloaded from the IEDB query API.
    repo_root = Path(__file__).resolve().parents[2]
    for candidate in (
        settings.storage_path / "evidence" / "iedb_ms_ligands.csv.bz2",
        repo_root / "storage" / "evidence" / "iedb_ms_ligands.csv.bz2",
    ):
        if candidate.exists():
            paths.append(str(candidate))

    # MHCflurry's bundled IEDB-derived measurements.
    try:
        from mhcflurry.downloads import get_path

        base = Path(get_path("models_class1_presentation")) / "models"
        candidate = base / "affinity_predictor_train_data.csv.bz2"
        if candidate.exists():
            paths.append(str(candidate))
    except Exception:  # noqa: BLE001
        pass

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def is_available() -> bool:
    return bool(_training_paths())


def status() -> dict:
    paths = _training_paths()
    return {
        "available": bool(paths),
        "sources": paths,
        "reason": None
        if paths
        else "No MS/ligand evidence source configured (EVIDENCE_MS_TRAINING).",
    }


def _load() -> tuple[set, set]:
    paths = tuple(_training_paths())
    if paths in _cache:
        return _cache[paths]
    ms_ligands: set[tuple[str, str]] = set()
    measured_binders: set[tuple[str, str]] = set()
    for path in paths:
        try:
            with bz2.open(path, "rt") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    allele = (row.get("allele") or "").strip()
                    peptide = (row.get("peptide") or "").strip().upper()
                    if not allele or not (8 <= len(peptide) <= 11):
                        continue
                    if any(ch not in _STANDARD_AA for ch in peptide):
                        continue
                    mtype = (row.get("measurement_type") or "").lower()
                    msrc = (row.get("measurement_source") or "").lower()
                    if (
                        "mass_spec" in mtype
                        or "mass spec" in mtype
                        or "mass_spec" in msrc
                        or "mass spec" in msrc
                        or "mass spectrometry" in msrc
                    ):
                        ms_ligands.add((allele, peptide))
                    try:
                        value = float(row.get("measurement_value"))
                    except (TypeError, ValueError):
                        value = None
                    if value is not None and value <= 500:
                        measured_binders.add((allele, peptide))
        except Exception:  # noqa: BLE001
            continue
    _cache[paths] = (ms_ligands, measured_binders)
    return _cache[paths]


def lookup(context: str | None, allele: str | None) -> dict:
    """Return evidence for any 8–11mer window of ``context`` at ``allele``."""
    if not context or not allele or not is_available():
        return {"observed": False, "kind": None, "peptide": None, "allele": allele}
    peptide = context.upper()
    ms_ligands, measured_binders = _load()
    for kind, pool in (("ms_ligand", ms_ligands), ("measured_binder", measured_binders)):
        for size in range(8, min(11, len(peptide)) + 1):
            for i in range(len(peptide) - size + 1):
                window = peptide[i : i + size]
                if (allele, window) in pool:
                    return {
                        "observed": True,
                        "kind": kind,
                        "peptide": window,
                        "allele": allele,
                    }
    return {"observed": False, "kind": None, "peptide": None, "allele": allele}
