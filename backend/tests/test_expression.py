from app.expression.identifiers import normalize_gene_id, normalize_transcript_id


def test_gene_id_version_strip():
    result = normalize_gene_id("ENSG00000141510.12")
    assert result.normalized == "ENSG00000141510"
    assert result.changed is True
    assert result.resolved is True
    assert result.method == "ensembl-gene-version-strip"


def test_gene_symbol_mapping_is_recorded():
    result = normalize_gene_id(None, gene_symbol="TP53")
    assert result.normalized == "ENSG00000141510"
    assert result.method == "gene-symbol-to-ensembl"
    assert result.changed is True


def test_unresolved_gene_id_is_preserved():
    result = normalize_gene_id("NOTAGENE")
    assert result.normalized == "NOTAGENE"
    assert result.resolved is False
    assert result.method == "unresolved"


def test_transcript_id_version_strip():
    result = normalize_transcript_id("ENST00000269305.9")
    assert result.normalized == "ENST00000269305"
    assert result.changed is True
    assert result.method == "ensembl-transcript-version-strip"


def test_missing_expression_is_unavailable(client, annotated_run):
    run_id = annotated_run["run_id"]
    body = client.get(f"/api/analysis-runs/{run_id}/expression/status").json()
    assert body["status"] == "EXPRESSION_UNAVAILABLE"
    assert body["total"] == 0


def test_expression_tsv_ingest_and_mapping(client, annotated_run, tmp_path):
    run_id = annotated_run["run_id"]
    path = tmp_path / "expression.tsv"
    path.write_text(
        "gene_id\tgene_symbol\ttranscript_id\texpression_value\tunit\n"
        "ENSG_MOCK00001.3\tMOCKGENE1\tENST_MOCK00001.1\t12.5\tTPM\n"
        "TP53\tTP53\t\t20.1\tTPM\n"
    )
    with open(path, "rb") as handle:
        body = client.post(
            f"/api/analysis-runs/{run_id}/expression/upload",
            files={"file": ("expression.tsv", handle, "text/tab-separated-values")},
        ).json()

    assert body["status"] == "EXPRESSION_AVAILABLE"
    assert body["valid"] == 2
    assert body["normalized_identifiers"] >= 2

    records = client.get(f"/api/analysis-runs/{run_id}/expression").json()
    by_symbol = {r["gene_symbol"]: r for r in records if r["gene_symbol"]}
    mock = by_symbol["MOCKGENE1"]
    assert mock["gene_id"] == "ENSG_MOCK00001"
    assert mock["gene_id_changed"] is True
    assert mock["transcript_id"] == "ENST_MOCK00001"
    assert mock["transcript_id_changed"] is True
    assert mock["input_hash"]
    tp53 = by_symbol["TP53"]
    assert tp53["gene_id"] == "ENSG00000141510"


def test_non_numeric_expression_is_invalid(client, annotated_run, tmp_path):
    run_id = annotated_run["run_id"]
    path = tmp_path / "bad.tsv"
    path.write_text("gene_symbol\texpression_value\nMOCKGENE1\tnot-a-number\n")
    with open(path, "rb") as handle:
        body = client.post(
            f"/api/analysis-runs/{run_id}/expression/upload",
            files={"file": ("bad.tsv", handle, "text/tab-separated-values")},
        ).json()
    assert body["status"] == "EXPRESSION_INVALID"
    assert body["invalid"] == 1


# ---- parser robustness (synthetic fixtures) ---------------------------------

from app.expression.parsing import parse_expression_records


def test_parse_skips_bom_comment_and_blank_lines():
    content = (
        "\ufeff# SYNTHETIC TEST DATA ONLY\n"
        "\n"
        "gene_id\tgene_symbol\texpression_value\tunit\n"
        "ENSGSYNTH00000000001\tSYNTHGENE00001\t0.1588\tsynthetic_TPM\n"
        "\n"
        "ENSGSYNTH00000000002\tSYNTHGENE00002\t0.2176\tsynthetic_TPM\n"
    )
    records = parse_expression_records(content, "tsv")
    assert len(records) == 2
    assert records[0]["gene_id"] == "ENSGSYNTH00000000001"
    assert records[0]["expression_value"] == "0.1588"
    assert records[0]["unit"] == "synthetic_TPM"


def test_parse_csv_with_comment_line():
    content = "# synthetic\ngene_id,expression_value\nENSGSYNTH1,3.5\n"
    records = parse_expression_records(content, "csv")
    assert records[0]["gene_id"] == "ENSGSYNTH1"
    assert records[0]["expression_value"] == "3.5"


def test_parse_only_comments_returns_empty():
    assert parse_expression_records("# only a comment\n\n", "tsv") == []


def test_expression_upload_with_leading_comment(client, annotated_run, tmp_path):
    run_id = annotated_run["run_id"]
    path = tmp_path / "synthetic_expression.tsv"
    path.write_text(
        "# SYNTHETIC TEST DATA ONLY\n"
        "gene_id\tgene_symbol\texpression_value\tunit\n"
        "ENSGSYNTH00000000001\tSYNTHGENE00001\t0.1588\tsynthetic_TPM\n"
        "ENSGSYNTH00000000002\tSYNTHGENE00002\t0.2176\tsynthetic_TPM\n"
    )
    with open(path, "rb") as handle:
        body = client.post(
            f"/api/analysis-runs/{run_id}/expression/upload",
            files={"file": ("synthetic_expression.tsv", handle, "text/tab-separated-values")},
        ).json()
    assert body["status"] == "EXPRESSION_AVAILABLE"
    assert body["valid"] == 2
