"""ClinVar clinical-significance provider (real data, local VCF).

Queries a local, bgzipped + tabix-indexed ClinVar VCF (e.g. the NCBI weekly
release ``clinvar.vcf.gz``) via pysam — fully offline at query time. Download
with ``scripts/download_clinvar_vcf.sh`` and point ``CLINVAR_EVIDENCE_VCF`` at
the file. Without the file the provider reports UNAVAILABLE; it never falls
back to the mock provider.
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.evidence.base import (
    EvidenceQuery,
    EvidenceResult,
    EvidenceStatus,
    EvidenceUnavailableError,
    VariantEvidenceProvider,
)
from app.evidence.registry import register_evidence_provider

_SIG_TERMS = {
    "Pathogenic": "Pathogenic",
    "Likely_pathogenic": "Likely pathogenic",
    "Uncertain_significance": "Uncertain significance",
    "Likely_benign": "Likely benign",
    "Benign": "Benign",
    "Conflicting_classifications_of_pathogenicity": "Conflicting interpretations",
}

_DRIVER_KEYWORDS = (
    "cancer",
    "carcinoma",
    "melanoma",
    "leukemia",
    "lymphoma",
    "sarcoma",
    "glioma",
    "neoplasm",
)


def _vcf_path() -> Path | None:
    explicit = (getattr(settings, "CLINVAR_EVIDENCE_VCF", "") or "").strip()
    if explicit and Path(explicit).is_file():
        return Path(explicit)
    for candidate in (
        settings.storage_path / "evidence" / "clinvar" / "clinvar.vcf.gz",
        settings.storage_path / "reference" / "clinvar.vcf.gz",
    ):
        if candidate.is_file():
            return candidate
    return None


def _version_from_header(path: Path) -> str:
    try:
        import gzip

        opener = gzip.open if str(path).endswith(".gz") else open
        with opener(path, "rt") as handle:
            for line in handle:
                if line.startswith("##fileDate="):
                    return line.split("=", 1)[1].strip()
                if not line.startswith("#"):
                    break
    except Exception:  # noqa: BLE001
        pass
    return "unknown"


def _parse_clnsig(value: str | None, alt_index: int = 0) -> str | None:
    """Parse CLNSIG.

    ``|`` separates allele-specific values (multiallelic rows); ``,`` separates
    multiple terms for one allele. ``alt_index`` selects the matched allele.
    """
    if not value or value == ".":
        return None
    alleles = value.split("|")
    chosen = alleles[alt_index] if alt_index < len(alleles) else alleles[0]
    terms = []
    for token in chosen.split(","):
        label = _SIG_TERMS.get(token.strip(), token.strip().replace("_", " "))
        terms.append(label)
    return "; ".join(dict.fromkeys(t for t in terms if t)) or None


def _parse_clndn(value: str | None) -> list[str]:
    if not value or value == ".":
        return []
    return [item.strip() for item in value.replace("_", " ").split("|") if item.strip()]


@register_evidence_provider
class ClinvarEvidenceProvider(VariantEvidenceProvider):
    provider_name = "clinvar"
    provider_version = "weekly-release"
    is_mock = False
    description = (
        "Real ClinVar clinical significance from a local tabix-indexed VCF "
        "(NCBI weekly release). Fully offline at query time."
    )
    supported_builds = ("GRCh37", "GRCh38")

    def health_check(self) -> EvidenceStatus:
        path = _vcf_path()
        if path is None:
            return EvidenceStatus.UNAVAILABLE
        try:
            import pysam

            pysam.TabixFile(str(path))
        except Exception:  # noqa: BLE001
            return EvidenceStatus.FAILED
        return EvidenceStatus.AVAILABLE

    def query(self, q: EvidenceQuery) -> EvidenceResult:
        path = _vcf_path()
        if path is None:
            raise EvidenceUnavailableError(
                "ClinVar VCF not installed. Run scripts/download_clinvar_vcf.sh "
                "and set CLINVAR_EVIDENCE_VCF."
            )
        if not q.chromosome or not q.position:
            raise EvidenceUnavailableError("Incomplete variant coordinates.")
        import pysam

        chrom = q.chromosome.replace("chr", "")
        region = f"{chrom}:{q.position}-{q.position}"
        matched: list[tuple[int, str, str, dict]] = []
        try:
            tabix = pysam.TabixFile(str(path))
            try:
                for row in tabix.fetch(region, parser=pysam.asTuple()):
                    if len(row) < 8:
                        continue
                    ref = row[3].upper()
                    info = _split_info(row[7])
                    for alt_index, alt in enumerate(a.upper() for a in row[4].split(",")):
                        if alt in (".", "*", ""):
                            continue
                        if (q.reference or "").upper() and ref != (q.reference or "").upper():
                            continue
                        if (q.alternate or "").upper() and alt != (q.alternate or "").upper():
                            continue
                        matched.append((int(row[1]), alt_index, ref, info))
            finally:
                tabix.close()
        except ValueError:
            # Region outside the indexed contigs → variant absent from ClinVar.
            matched = []
        except Exception as exc:  # noqa: BLE001
            raise EvidenceUnavailableError(f"ClinVar lookup failed: {exc}") from exc

        if not matched:
            return EvidenceResult(
                provider=self.provider_name,
                source=f"ClinVar VCF ({_version_from_header(path)})",
                provider_version=self.provider_version,
                population_frequency=None,
                known_driver=None,
                clinical_significance=None,
                identifiers=[],
                status=EvidenceStatus.AVAILABLE.value,
                detail={"observed": False},
            )

        _pos, alt_index, _ref, info = matched[0]
        accession = info.get("ALLELEID")
        identifiers = [f"VCV{accession}"] if accession else []
        if info.get("RS"):
            identifiers.append(f"rs{info['RS']}")
        conditions = _parse_clndn(info.get("CLNDN"))
        significance = _parse_clnsig(info.get("CLNSIG"), alt_index)
        known_driver = None
        if significance and "Pathogenic" in significance and conditions:
            if any(
                any(keyword in condition.lower() for keyword in _DRIVER_KEYWORDS)
                for condition in conditions
            ):
                known_driver = True
        return EvidenceResult(
            provider=self.provider_name,
            source=f"ClinVar VCF ({_version_from_header(path)})",
            provider_version=self.provider_version,
            population_frequency=None,
            known_driver=known_driver,
            clinical_significance=significance,
            identifiers=identifiers[:10],
            status=EvidenceStatus.AVAILABLE.value,
            detail={
                "observed": True,
                "accession": accession,
                "conditions": conditions[:10],
                "review_status": info.get("CLNREVSTAT"),
            },
        )


def _split_info(field: str) -> dict[str, str]:
    info: dict[str, str] = {}
    for token in field.split(";"):
        if "=" in token:
            key, value = token.split("=", 1)
            info[key] = value
        elif token:
            info[token] = "true"
    return info
