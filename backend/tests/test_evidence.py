"""Tests for the variant evidence engine (gnomAD / ClinVar / COSMIC / mock)."""

import gzip
import os

import pytest

from app.evidence.base import (
    EvidenceQuery,
    EvidenceStatus,
    EvidenceUnavailableError,
)
from app.evidence.clinvar import (
    _parse_clndn,
    _parse_clnsig,
    ClinvarEvidenceProvider,
)
from app.evidence.gnomad import (
    _population_frequency,
    _variant_id,
    GnomadEvidenceProvider,
)
from app.evidence.mock import MockEvidenceProvider
from app.evidence.registry import get_evidence_provider, list_evidence_providers


# ---- provider registry -------------------------------------------------------


def test_providers_registered():
    names = {p["name"] for p in list_evidence_providers()}
    assert names == {"mock", "gnomad", "clinvar", "cosmic"}


def test_mock_provider_deterministic():
    provider = MockEvidenceProvider()
    assert provider.health_check() == EvidenceStatus.MOCK
    q = EvidenceQuery("1", 55516888, "G", "A", "GRCh38")
    first = provider.query(q)
    second = provider.query(q)
    assert first.population_frequency == second.population_frequency
    assert first.status == "MOCK"
    assert first.population_frequency is not None
    assert 0.0 <= first.population_frequency < 0.01


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        get_evidence_provider("cosmicdb")


def test_gnomad_variant_id_and_population():
    q = EvidenceQuery("chr1", 55516888, "g", "a", "GRCh38")
    assert _variant_id(q) == "1-55516888-G-A"
    assert _variant_id(EvidenceQuery(None, None, None, None, "GRCh38")) is None

    node = {"populations": [{"id": "afr", "ac": 100, "an": 1000}, {"id": "global", "ac": 25, "an": 500}]}
    af, pop = _population_frequency(node)
    assert af == 0.05 and pop == "global"

    node = {"populations": [{"id": "afr", "ac": 100, "an": 1000}]}
    af, pop = _population_frequency(node)
    assert af == 0.1 and pop == "afr"

    assert _population_frequency(None) == (None, None)
    assert _population_frequency({"populations": []}) == (None, None)


# ---- gnomAD provider (fake HTTP) --------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def json(self):
        return self._payload


def _gnomad_payload(ac=40, an=100000, dataset="gnomad_r4"):
    return {
        "data": {
            "variant": {
                "variantId": "1-55516888-G-A",
                "genome": {"populations": [{"id": "global", "ac": ac, "an": an}]},
                "exome": None,
            }
        }
    }


def test_gnomad_query_real_flow(monkeypatch, tmp_path):
    calls = []

    def fake_post(client, variant_id, dataset):
        calls.append(dataset)
        return _FakeResponse(_gnomad_payload(dataset=dataset))

    monkeypatch.setattr("app.evidence.gnomad._post", fake_post)
    monkeypatch.setattr("app.evidence.gnomad.settings.STORAGE_DIR", str(tmp_path))
    provider = GnomadEvidenceProvider()
    q = EvidenceQuery("1", 55516888, "G", "A", "GRCh38")
    result = provider.query(q)
    assert result.population_frequency == 0.0004
    assert result.source == "gnomAD gnomad_r4"
    assert result.status == "AVAILABLE"
    assert calls == ["gnomad_r4"]

    # Second call served from cache (no new HTTP request).
    result2 = provider.query(q)
    assert result2.population_frequency == 0.0004
    assert calls == ["gnomad_r4"]


def test_gnomad_grch37_dataset(monkeypatch):
    calls = []

    def fake_post(client, variant_id, dataset):
        calls.append(dataset)
        return _FakeResponse(_gnomad_payload(dataset=dataset))

    monkeypatch.setattr("app.evidence.gnomad._post", fake_post)
    provider = GnomadEvidenceProvider()
    provider.query(EvidenceQuery("1", 55516888, "G", "A", "GRCh37"))
    assert calls == ["gnomad_r2_1"]


def test_gnomad_api_failure_raises(monkeypatch):
    monkeypatch.setattr(
        "app.evidence.gnomad._post",
        lambda client, vid, ds: (_ for _ in ()).throw(
            EvidenceUnavailableError("gnomAD API failed after retries: HTTP 500")
        ),
    )
    provider = GnomadEvidenceProvider()
    with pytest.raises(EvidenceUnavailableError):
        provider.query(EvidenceQuery("1", 1, "A", "G", "GRCh38"))


def test_gnomad_variant_not_in_dataset_records_absent(monkeypatch, tmp_path):
    def fake_post(client, variant_id, dataset):
        return _FakeResponse({"data": {"variant": None}})

    monkeypatch.setattr("app.evidence.gnomad._post", fake_post)
    monkeypatch.setattr("app.evidence.gnomad.settings.STORAGE_DIR", str(tmp_path))
    provider = GnomadEvidenceProvider()
    result = provider.query(EvidenceQuery("9", 123456, "A", "G", "GRCh38"))
    assert result.status == "AVAILABLE"
    assert result.population_frequency is None
    assert result.detail["observed"] is False


def test_gnomad_incomplete_coordinates():
    provider = GnomadEvidenceProvider()
    with pytest.raises(EvidenceUnavailableError):
        provider.query(EvidenceQuery(None, 1, "A", "G", "GRCh38"))


# ---- ClinVar provider (local VCF) ------------------------------------------


_VCF_HEADER = (
    "##fileformat=VCFv4.2\n"
    "##fileDate=2026-09-30\n"
    "##INFO=<ID=ALLELEID,Number=1,Type=Integer,Description=\"allele id\">\n"
    "##INFO=<ID=CLNSIG,Number=.,Type=String,Description=\"clinical significance\">\n"
    "##INFO=<ID=CLNDN,Number=.,Type=String,Description=\"conditions\">\n"
    "##INFO=<ID=CLNREVSTAT,Number=.,Type=String,Description=\"review status\">\n"
    "##INFO=<ID=RS,Number=1,Type=String,Description=\"dbSNP id\">\n"
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
)

_ROWS = [
    "1\t100\t.\tA\tG\t.\t.\tALLELEID=12345;CLNSIG=Pathogenic;CLNDN=Lung_cancer;CLNREVSTAT=reviewed_by_expert_panel;RS=7777\n",
    "1\t200\t.\tC\tT\t.\t.\tALLELEID=99999;CLNSIG=Benign;CLNDN=not_specified;CLNREVSTAT=criteria_provided\n",
    "2\t300\t.\tG\tA\t.\t.\tALLELEID=111;CLNSIG=Uncertain_significance;CLNDN=Melanoma;CLNREVSTAT=criteria_provided\n",
]


@pytest.fixture
def clinvar_vcf(tmp_path, monkeypatch):
    import pysam

    raw = tmp_path / "clinvar.vcf"
    raw.write_text(_VCF_HEADER + "".join(_ROWS))
    compressed = tmp_path / "clinvar.vcf.gz"
    pysam.tabix_compress(str(raw), str(compressed), force=True)
    pysam.tabix_index(str(compressed), preset="vcf", force=True)
    monkeypatch.setattr("app.evidence.clinvar.settings.CLINVAR_EVIDENCE_VCF", str(compressed))
    return str(compressed)


def test_clinvar_health_check_unavailable_by_default(monkeypatch, tmp_path):
    from app.core.config import Settings

    provider = ClinvarEvidenceProvider()
    assert provider.health_check() == EvidenceStatus.UNAVAILABLE


def test_clinvar_query_match(clinvar_vcf):
    provider = ClinvarEvidenceProvider()
    assert provider.health_check() == EvidenceStatus.AVAILABLE
    result = provider.query(EvidenceQuery("1", 100, "A", "G", "GRCh38"))
    assert result.clinical_significance == "Pathogenic"
    assert result.known_driver is True  # pathogenic + cancer condition
    assert "VCV12345" in result.identifiers
    assert "rs7777" in result.identifiers
    assert result.detail["conditions"] == ["Lung cancer"]


def test_clinvar_query_benign_not_driver(clinvar_vcf):
    provider = ClinvarEvidenceProvider()
    result = provider.query(EvidenceQuery("1", 200, "C", "T", "GRCh38"))
    assert result.clinical_significance == "Benign"
    assert result.known_driver is False or result.known_driver is None
    assert result.population_frequency is None


def test_clinvar_query_absent(clinvar_vcf):
    provider = ClinvarEvidenceProvider()
    result = provider.query(EvidenceQuery("9", 42, "A", "C", "GRCh38"))
    assert result.clinical_significance is None
    assert result.detail["observed"] is False


def test_clinvar_parse_helpers():
    assert _parse_clnsig("Pathogenic") == "Pathogenic"
    assert _parse_clnsig("Pathogenic,Likely_pathogenic") == "Pathogenic; Likely pathogenic"
    assert _parse_clnsig("Pathogenic|Benign", alt_index=0) == "Pathogenic"
    assert _parse_clnsig("Pathogenic|Benign", alt_index=1) == "Benign"
    assert _parse_clnsig(".") is None
    assert _parse_clndn("Lung_cancer|Melanoma") == ["Lung cancer", "Melanoma"]
    assert _parse_clndn(".") == []


# ---- API level ---------------------------------------------------------------


def _ready_run(client, name):
    project_id = client.post("/api/projects", json={"name": name}).json()["id"]
    integration = client.post(f"/api/projects/{project_id}/synthetic-integration").json()
    return integration["analysis_run_id"]


def test_evidence_providers_endpoint(client):
    response = client.get("/api/evidence/providers")
    assert response.status_code == 200
    by_name = {p["name"]: p for p in response.json()}
    assert by_name["mock"]["status"] == "MOCK"
    assert by_name["cosmic"]["status"] == "UNAVAILABLE"


def test_annotate_run_with_mock(client):
    run_id = _ready_run(client, "Evidence Project")
    response = client.post(f"/api/analysis-runs/{run_id}/evidence", json={"providers": ["mock"]})
    assert response.status_code == 200
    body = response.json()
    assert body["records_written"] > 0
    assert body["variants_considered"] > 0
    assert all(r["provider"] == "mock" for r in body["results"])

    records = client.get(f"/api/analysis-runs/{run_id}/evidence").json()
    assert records
    assert {r["provider"] for r in records} == {"mock"}
    assert all(r["status"] == "MOCK" for r in records)
    has_freq = any(r["population_frequency"] is not None for r in records)
    assert has_freq


def test_annotate_run_with_unknown_provider_400(client):
    run_id = _ready_run(client, "Evidence Bad Provider")
    response = client.post(
        f"/api/analysis-runs/{run_id}/evidence", json={"providers": ["cosmicdb"]}
    )
    assert response.status_code == 400


def test_annotate_skips_unavailable_provider(client):
    run_id = _ready_run(client, "Evidence Skip")
    response = client.post(
        f"/api/analysis-runs/{run_id}/evidence", json={"providers": ["clinvar"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["records_written"] == 0
    assert body["skipped_providers"][0]["provider"] == "clinvar"


def test_gnomad_failure_recorded_as_failed(client, monkeypatch):
    monkeypatch.setattr(
        "app.evidence.gnomad._post",
        lambda client, vid, ds: (_ for _ in ()).throw(
            EvidenceUnavailableError("gnomAD API failed after retries: HTTP 503")
        ),
    )
    run_id = _ready_run(client, "Evidence gnomAD Fail")
    response = client.post(f"/api/analysis-runs/{run_id}/evidence", json={"providers": ["gnomad"]})
    assert response.status_code == 200
    body = response.json()
    assert body["records_written"] == 0
    assert len(body["failed_lookups"]) > 0
    records = client.get(f"/api/analysis-runs/{run_id}/evidence").json()
    assert records and all(r["status"] == "FAILED" for r in records)


def test_variant_detail_includes_evidence(client):
    run_id = _ready_run(client, "Evidence Detail")
    variants = client.get(f"/api/analysis-runs/{run_id}/variants").json()
    variant_id = variants[0]["id"]
    client.post(f"/api/analysis-runs/{run_id}/evidence", json={"providers": ["mock"]})
    detail = client.get(f"/api/analysis-runs/{run_id}/variants/{variant_id}").json()
    assert detail["evidence"] is not None
    if detail["evidence"]:
        record = detail["evidence"][0]
        assert record["provider"] == "mock"


def test_manifest_lists_evidence_providers(client):
    manifest = client.get("/api/system/manifest").json()
    providers = manifest.get("variant_evidence_providers") or []
    names = {p["name"] for p in providers}
    assert {"mock", "gnomad", "clinvar", "cosmic"} <= names
