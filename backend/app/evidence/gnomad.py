"""gnomAD population-frequency provider (real data).

Uses the official gnomAD GraphQL API (no key required):

- GRCh38 → dataset ``gnomad_r4`` (fallback ``gnomad_r3``)
- GRCh37 → dataset ``gnomad_r2_1``

Population frequency is computed as ``AC/AN`` for the global genome
population (exome used when no genome call exists). Responses are cached on
disk under ``storage/evidence_cache/gnomad/``. If the API is unreachable the
lookup raises ``EvidenceUnavailableError`` — it never falls back to the mock
provider.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import httpx

from app.core.config import settings
from app.evidence.base import (
    EvidenceQuery,
    EvidenceResult,
    EvidenceStatus,
    EvidenceUnavailableError,
    VariantEvidenceProvider,
)
from app.evidence.registry import register_evidence_provider

_BASE_URL = "https://gnomad.broadinstitute.org/api/"

_DATASETS_BY_BUILD = {
    "GRCh38": ("gnomad_r4", "gnomad_r3"),
    "GRCh37": ("gnomad_r2_1",),
}

_QUERY = """
query VariantEvidence($variantId: String!, $dataset: DatasetId!) {
  variant(variantId: $variantId, dataset: $dataset) {
    variantId
    genome { populations { id ac an } }
    exome { populations { id ac an } }
  }
}
"""


def _variant_id(q: EvidenceQuery) -> str | None:
    if not q.chromosome or not q.position or not q.reference or not q.alternate:
        return None
    chrom = q.chromosome.replace("chr", "")
    return f"{chrom}-{q.position}-{q.reference.upper()}-{q.alternate.upper()}"


def _cache_file(q: EvidenceQuery) -> Path:
    digest = hashlib.sha256(
        f"{q.reference_build}|{_variant_id(q)}".encode()
    ).hexdigest()[:16]
    return settings.storage_path / "evidence_cache" / "gnomad" / f"{digest}.json"


def _read_cache(q: EvidenceQuery) -> dict | None:
    path = _cache_file(q)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return None


def _write_cache(q: EvidenceQuery, entry: dict) -> None:
    try:
        path = _cache_file(q)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entry))
    except Exception:  # noqa: BLE001
        pass


def _post(client: httpx.Client, variant_id: str, dataset: str) -> httpx.Response:
    last = "unknown error"
    for attempt in range(4):
        try:
            response = client.post(
                _BASE_URL,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "query": _QUERY,
                    "variables": {"variantId": variant_id, "dataset": dataset},
                },
                timeout=20.0,
            )
            if response.status_code == 200:
                return response
            last = f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(2 * (attempt + 1))
    raise EvidenceUnavailableError(f"gnomAD API failed after retries: {last}")


def _population_frequency(node: dict | None) -> tuple[float | None, str | None]:
    if not node:
        return None, None
    populations = node.get("populations") or []
    if not populations:
        return None, None
    chosen = next(
        (p for p in populations if (p.get("id") or "") in ("global", "gnomad:global")),
        max(populations, key=lambda p: p.get("an") or 0),
    )
    ac = chosen.get("ac")
    an = chosen.get("an")
    if ac is None or not an:
        return None, chosen.get("id")
    return round(float(ac) / float(an), 6), chosen.get("id")


@register_evidence_provider
class GnomadEvidenceProvider(VariantEvidenceProvider):
    provider_name = "gnomad"
    provider_version = "r4/r3/r2.1 (REST)"
    is_mock = False
    description = (
        "Real gnomAD population frequency via the official GraphQL API "
        "(GRCh38 → r4, GRCh37 → r2.1). No API key required."
    )
    supported_builds = ("GRCh37", "GRCh38")

    def health_check(self) -> EvidenceStatus:
        return EvidenceStatus.AVAILABLE

    def query(self, q: EvidenceQuery) -> EvidenceResult:
        variant_id = _variant_id(q)
        if variant_id is None:
            raise EvidenceUnavailableError("Incomplete variant coordinates.")
        cached = _read_cache(q)
        if cached is not None:
            return EvidenceResult(**cached)

        datasets = _DATASETS_BY_BUILD.get(q.reference_build, ("gnomad_r4",))
        last_error = None
        with httpx.Client(timeout=20.0) as client:
            for dataset in datasets:
                try:
                    response = _post(client, variant_id, dataset)
                    payload = response.json()
                    variant = (payload.get("data") or {}).get("variant")
                    if not variant:
                        # Variant absent from this dataset's call set: record
                        # "not observed" (frequency None) — not a failure.
                        absent = EvidenceResult(
                            provider=self.provider_name,
                            source=f"gnomAD {dataset}",
                            provider_version=self.provider_version,
                            population_frequency=None,
                            known_driver=None,
                            clinical_significance=None,
                            identifiers=[],
                            status=EvidenceStatus.AVAILABLE.value,
                            detail={"dataset": dataset, "observed": False},
                        )
                        _write_cache(q, _result_to_dict(absent))
                        return absent
                    af, pop = _population_frequency(variant.get("genome"))
                    if af is None:
                        af, pop = _population_frequency(variant.get("exome"))
                    result = EvidenceResult(
                        provider=self.provider_name,
                        source=f"gnomAD {dataset}",
                        provider_version=self.provider_version,
                        population_frequency=af,
                        known_driver=None,
                        clinical_significance=None,
                        identifiers=[],
                        status=EvidenceStatus.AVAILABLE.value,
                        detail={"dataset": dataset, "population": pop},
                    )
                    _write_cache(q, _result_to_dict(result))
                    return result
                except EvidenceUnavailableError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    last_error = f"{type(exc).__name__}: {exc}"
        raise EvidenceUnavailableError(f"gnomAD lookup failed: {last_error}")


def _result_to_dict(result: EvidenceResult) -> dict:
    return {
        "provider": result.provider,
        "source": result.source,
        "provider_version": result.provider_version,
        "population_frequency": result.population_frequency,
        "known_driver": result.known_driver,
        "clinical_significance": result.clinical_significance,
        "identifiers": result.identifiers,
        "status": result.status,
        "detail": result.detail,
    }
