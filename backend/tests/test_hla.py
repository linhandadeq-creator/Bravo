from app.hla.normalization import normalize_hla_allele, parse_hla_records


def test_valid_class_i_normalization():
    result = normalize_hla_allele("HLA-A*02:01")
    assert result.valid is True
    assert result.normalized == "HLA-A*02:01"
    assert result.locus == "A"
    assert result.allele_class == "I"


def test_valid_class_ii_normalization():
    result = normalize_hla_allele("DRB1*15:01")
    assert result.valid is True
    assert result.normalized == "HLA-DRB1*15:01"
    assert result.allele_class == "II"


def test_compact_allele_format_is_normalized():
    result = normalize_hla_allele("A0201")
    assert result.valid is True
    assert result.normalized == "HLA-A*02:01"


def test_invalid_allele_is_rejected():
    result = normalize_hla_allele("HLA-Z*01:01")
    assert result.valid is False
    assert "unknown HLA locus" in (result.reason or "")

    malformed = normalize_hla_allele("HLA-A*XX:01")
    assert malformed.valid is False

    empty = normalize_hla_allele("")
    assert empty.valid is False


def test_class_mismatch_is_rejected():
    result = normalize_hla_allele("HLA-A*02:01", declared_class="II")
    assert result.valid is False
    assert "class mismatch" in (result.reason or "")


def test_parse_json_records():
    content = (
        '{"alleles":[{"allele":"HLA-A*02:01","class":"I"},'
        '{"allele":"HLA-DQB1*06:02","class":"II"}]}'
    )
    records = parse_hla_records(content, "json")
    assert records[0]["allele"] == "HLA-A*02:01"
    assert records[0]["declared_class"] == "I"
    assert records[1]["allele"] == "HLA-DQB1*06:02"


def test_parse_tsv_records():
    content = "allele\tclass\tsource\tmethod\nHLA-B*07:02\tI\tsynth\tmock\n"
    records = parse_hla_records(content, "tsv")
    assert records[0]["allele"] == "HLA-B*07:02"
    assert records[0]["source"] == "synth"


def _alleles(*specs):
    return [{"allele": a, "class": c} for a, c in specs]


def test_manual_ingest_and_status(client, annotated_run):
    run_id = annotated_run["run_id"]
    response = client.post(
        f"/api/analysis-runs/{run_id}/hla",
        json={
            "alleles": _alleles(
                ("HLA-A*02:01", "I"),
                ("HLA-B*07:02", "I"),
                ("HLA-DRB1*15:01", "II"),
            ),
            "source": "manual",
            "method": "manual",
            "version": "1.0.0",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "HLA_AVAILABLE"
    assert body["valid"] == 3
    assert body["class_i"] == 2
    assert body["class_ii"] == 1

    profiles = client.get(f"/api/analysis-runs/{run_id}/hla").json()
    assert profiles[0]["normalization_method"]
    assert profiles[0]["input_hash"]


def test_duplicate_allele_detected(client, annotated_run):
    run_id = annotated_run["run_id"]
    body = client.post(
        f"/api/analysis-runs/{run_id}/hla",
        json={"alleles": _alleles(("HLA-A*02:01", "I"), ("A0201", "I"))},
    ).json()
    assert body["duplicate"] == 1
    assert body["valid"] == 2


def test_invalid_hla_makes_status_invalid(client, annotated_run):
    run_id = annotated_run["run_id"]
    body = client.post(
        f"/api/analysis-runs/{run_id}/hla",
        json={"alleles": _alleles(("HLA-A*02:01", "I"), ("HLA-A*02:01", "II"))},
    ).json()
    assert body["status"] == "HLA_INVALID"
    assert body["invalid"] == 1


def test_missing_hla_is_unavailable(client, annotated_run):
    run_id = annotated_run["run_id"]
    body = client.get(f"/api/analysis-runs/{run_id}/hla/status").json()
    assert body["status"] == "HLA_UNAVAILABLE"
    assert body["total"] == 0


def test_hla_upload_csv(client, annotated_run, tmp_path):
    run_id = annotated_run["run_id"]
    path = tmp_path / "hla.csv"
    path.write_text("allele,class\nHLA-A*02:01,I\nHLA-C*07:02,I\n")
    with open(path, "rb") as handle:
        body = client.post(
            f"/api/analysis-runs/{run_id}/hla/upload",
            files={"file": ("hla.csv", handle, "text/csv")},
        ).json()
    assert body["status"] == "HLA_AVAILABLE"
    assert body["valid"] == 2


# ---- parser robustness (synthetic fixtures) ---------------------------------

import pytest


def test_parse_headerless_single_column():
    content = "A*02:01\nA*24:02\nB*08:01\nC*03:04\n"  # synthetic
    records = parse_hla_records(content, "tsv")
    assert [r["allele"] for r in records] == ["A*02:01", "A*24:02", "B*08:01", "C*03:04"]


def test_parse_headerless_with_hla_prefix():
    content = "HLA-A*02:01\nHLA-DRB1*15:01\n"
    records = parse_hla_records(content, "tsv")
    assert [r["allele"] for r in records] == ["HLA-A*02:01", "HLA-DRB1*15:01"]


def test_parse_headerless_allele_and_class():
    content = "A*02:01\tI\nA*24:02\tI\nDRB1*15:01\tII\n"
    records = parse_hla_records(content, "tsv")
    assert records[0] == {"allele": "A*02:01", "declared_class": "I"}
    assert records[2]["declared_class"] == "II"


def test_parse_ignores_bom_comments_and_blank_lines():
    content = "\ufeff# exported by typing tool\n\nA*02:01\n\nB*08:01\n"
    records = parse_hla_records(content, "tsv")
    assert [r["allele"] for r in records] == ["A*02:01", "B*08:01"]


def test_parse_header_aliases():
    for header in ("allele", "Allele Name", "hla_allele", "HLA", "value"):
        content = f"{header}\tclass\nA*02:01\tI\n"
        records = parse_hla_records(content, "tsv")
        assert records[0]["allele"] == "A*02:01", header


def test_parse_wide_format_reports_missing_allele_column():
    content = "A1\tA2\tB1\tB2\nA*02:01\tA*24:02\tB*08:01\tB*07:02\n"
    with pytest.raises(ValueError) as excinfo:
        parse_hla_records(content, "tsv")
    message = str(excinfo.value)
    assert "Could not locate an 'allele' column" in message
    assert "A1" in message  # the offending columns are reported


def test_parse_header_without_allele_column_reports_columns():
    content = "gene\tcount\nA\t2\n"
    with pytest.raises(ValueError) as excinfo:
        parse_hla_records(content, "csv")
    assert "gene" in str(excinfo.value)


# ---- individual allele normalization (synthetic) ----------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("HLA-A*02:01", "HLA-A*02:01"),
        ("A*02:01", "HLA-A*02:01"),
        ("a*02:01", "HLA-A*02:01"),
        ("  A*02:01  ", "HLA-A*02:01"),
        ("A0201", "HLA-A*02:01"),
        ("A*2:1", "HLA-A*02:01"),
        ("A*02:01:01", "HLA-A*02:01:01"),
        ("DRB1*15:01", "HLA-DRB1*15:01"),
        ("DQB1*06:02", "HLA-DQB1*06:02"),
        ("DPB1*04:01", "HLA-DPB1*04:01"),
    ],
)
def test_normalize_supported_formats(raw, expected):
    result = normalize_hla_allele(raw)
    assert result.valid is True, (raw, result.reason)
    assert result.normalized == expected


@pytest.mark.parametrize(
    "raw,reason_fragment",
    [
        ("", "empty"),
        (None, "empty"),
        ("   ", "empty"),
        ("HLA-A", "missing allele fields"),
        ("HLA-A*", "missing allele fields"),
        ("HLA-A*XX:01", "numeric"),
        ("HLA-Z*01:01", "unknown HLA locus"),
        ("HLA-A*02", "at least two fields"),
        ("not-an-allele", "missing allele fields"),
    ],
)
def test_normalize_invalid_formats(raw, reason_fragment):
    result = normalize_hla_allele(raw)
    assert result.valid is False
    assert reason_fragment.lower() in (result.reason or "").lower()


def test_normalize_unknown_class_value():
    result = normalize_hla_allele("HLA-A*02:01", declared_class="III")
    assert result.valid is False
    assert "unknown HLA class" in (result.reason or "")


# ---- API integration (synthetic) --------------------------------------------


def test_upload_headerless_tsv(client, annotated_run, tmp_path):
    run_id = annotated_run["run_id"]
    path = tmp_path / "synthetic_hla.tsv"
    path.write_text("A*02:01\nA*24:02\nB*08:01\nC*03:04\n")  # synthetic
    with open(path, "rb") as handle:
        body = client.post(
            f"/api/analysis-runs/{run_id}/hla/upload",
            files={"file": ("synthetic_hla.tsv", handle, "text/tab-separated-values")},
        ).json()
    assert body["status"] == "HLA_AVAILABLE"
    assert body["valid"] == 4
    assert body["class_i"] == 4


def test_upload_bad_column_returns_400(client, annotated_run, tmp_path):
    run_id = annotated_run["run_id"]
    path = tmp_path / "synthetic_wide.tsv"
    path.write_text("A1\tA2\nA*02:01\tA*24:02\n")  # synthetic, unsupported shape
    with open(path, "rb") as handle:
        response = client.post(
            f"/api/analysis-runs/{run_id}/hla/upload",
            files={"file": ("synthetic_wide.tsv", handle, "text/tab-separated-values")},
        )
    assert response.status_code == 400
    assert "allele" in response.json()["detail"].lower()


def test_invalid_allele_message_names_the_value(client, annotated_run):
    run_id = annotated_run["run_id"]
    body = client.post(
        f"/api/analysis-runs/{run_id}/hla",
        json={"alleles": [{"allele": "HLA-A*02:01", "class": "I"}, {"allele": "HLA-Z*99:99", "class": "I"}]},
    ).json()
    assert body["status"] == "HLA_INVALID"
    assert "HLA-Z*99:99" in body["message"]
    assert "unknown HLA locus" in body["message"]


def test_failed_upload_keeps_existing_hla(client, annotated_run, tmp_path):
    run_id = annotated_run["run_id"]
    # Seed valid data.
    good = client.post(
        f"/api/analysis-runs/{run_id}/hla",
        json={"alleles": [{"allele": "HLA-A*02:01", "class": "I"}]},
    ).json()
    assert good["status"] == "HLA_AVAILABLE"

    # A malformed re-upload must fail without wiping the existing profiles.
    bad = tmp_path / "synthetic_bad.tsv"
    bad.write_text("gene\tcount\nA\t2\n")
    with open(bad, "rb") as handle:
        response = client.post(
            f"/api/analysis-runs/{run_id}/hla/upload",
            files={"file": ("synthetic_bad.tsv", handle, "text/tab-separated-values")},
        )
    assert response.status_code == 400

    after = client.get(f"/api/analysis-runs/{run_id}/hla/status").json()
    assert after["status"] == "HLA_AVAILABLE"
    assert after["total"] == 1


def test_invalid_hla_blocks_readiness(client, annotated_run):
    run_id = annotated_run["run_id"]
    client.post(
        f"/api/analysis-runs/{run_id}/hla",
        json={"alleles": [{"allele": "HLA-Z*01:01", "class": "I"}]},
    )
    readiness = client.get(f"/api/analysis-runs/{run_id}/neoantigen-readiness")
    assert readiness.status_code == 409
