import io

import pytest

from app.core.config import settings
from app.services import uploads


def test_copy_limited_enforces_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 16)
    destination = tmp_path / "big.vcf"
    with pytest.raises(uploads.UploadTooLargeError):
        uploads.copy_limited(io.BytesIO(b"A" * 100), destination)
    # Partial file must be removed.
    assert not destination.exists()


def test_read_bytes_limited_uses_text_limit(monkeypatch):
    monkeypatch.setattr(settings, "MAX_TEXT_UPLOAD_BYTES", 8)
    # The streamed limit is irrelevant to in-memory text reads.
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 10**12)
    with pytest.raises(uploads.UploadTooLargeError):
        uploads.read_bytes_limited(io.BytesIO(b"A" * 100))


def test_text_upload_within_limit_is_read(monkeypatch):
    monkeypatch.setattr(settings, "MAX_TEXT_UPLOAD_BYTES", 1024)
    assert uploads.read_bytes_limited(io.BytesIO(b"A" * 100)) == b"A" * 100


def test_default_limits_cover_wgs_and_cap_in_memory_text():
    # Streamed VCF uploads must accommodate whole-genome tumour/normal VCFs.
    assert settings.MAX_UPLOAD_BYTES >= 3 * 1024 * 1024 * 1024
    # In-memory HLA/expression text must stay small to avoid OOM.
    assert settings.MAX_TEXT_UPLOAD_BYTES <= 128 * 1024 * 1024


def test_upload_endpoint_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 32)
    project_id = client.post("/api/projects", json={"name": "Upload limit"}).json()["id"]

    vcf = (
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "chr1\t1003\t.\tA\tG\t.\tPASS\t.\n"
    )
    response = client.post(
        "/api/analysis-runs/upload",
        data={"project_id": project_id, "reference_build": "GRCh38"},
        files={"tumor_file": ("tumor.vcf", io.BytesIO(vcf.encode() * 10), "text/plain")},
    )
    assert response.status_code == 413
    assert "maximum size" in response.json()["detail"].lower()
