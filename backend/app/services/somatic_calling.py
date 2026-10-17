"""Upstream somatic-calling capability status.

The platform accepts pre-called VCFs. Calling variants directly from aligned
reads (BAM/CRAM) requires an external toolchain — an aligner (BWA-MEM2),
samtools, Mutect2 (GATK) and a local reference genome — plus purity/ploidy and
contamination estimation. None of that ships with the platform; this module
reports exactly which components are present so the stage is never claimed as
available when it is not.
"""
from __future__ import annotations

import os

from app.core.config import settings


def _executable(path: str) -> bool:
    path = (path or "").strip()
    return bool(path) and os.path.isfile(path) and os.access(path, os.X_OK)


def _file(path: str) -> bool:
    path = (path or "").strip()
    return bool(path) and os.path.isfile(path)


def status() -> dict:
    try:
        import pysam  # noqa: F401

        pysam_ok = True
    except Exception:  # noqa: BLE001
        pysam_ok = False

    components = {
        "bwa": _executable(settings.SOMATIC_BWA_BIN),
        "gatk_mutect2": _executable(settings.SOMATIC_GATK_BIN),
        "reference_genome": _file(settings.SOMATIC_REFERENCE_FASTA),
        "pysam": pysam_ok,
    }
    available = components["bwa"] and components["gatk_mutect2"] and components["reference_genome"]
    missing = [name for name, ok in components.items() if not ok]
    return {
        "available": available,
        "components": components,
        "note": (
            "Upstream BAM/CRAM → somatic calling, purity/ploidy and contamination "
            "estimation are provided by external tools and are not bundled."
        ),
        "reason": None
        if available
        else "Missing: " + ", ".join(missing) + ". The platform accepts pre-called VCFs.",
    }
