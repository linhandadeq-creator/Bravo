def test_one_click_demo_generates_blueprint(client):
    response = client.post(
        "/api/one-click/generate",
        data={"demo": "true", "project_name": "一键演示项目", "top_n": "3"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "SUCCESS"
    assert result["construct_id"]
    assert result["report_id"]
    assert result["candidate_count"] >= 1
    assert result["blueprint"]["segments"][0]["type"] == "5PRIME"
    assert result["blueprint"]["segments"][-1]["type"] == "3PRIME"
    antigen = [s for s in result["blueprint"]["segments"] if s["type"] == "ANTIGEN"]
    assert antigen
    assert antigen[0]["gene"]
    assert result["blueprint"]["sequence"]
    assert "Research schematic" in result["disclaimer"]

    stage_names = {s["step"] for s in result["stages"]}
    assert {"VCF_QC", "ANNOTATION", "HLA_EXPRESSION", "NEOANTIGEN", "CONSTRUCT", "REPORT"} <= stage_names


def test_one_click_upload_without_normal_is_blocked(client, tmp_path):
    tumor = tmp_path / "t.vcf"
    tumor.write_text(
        "##fileformat=VCFv4.2\n"
        "##contig=<ID=chr1,length=248956422>\n"
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS\n"
        "chr1\t1003\t.\tA\tG\t60\tPASS\t.\tGT\t0/1\n"
    )
    with open(tumor, "rb") as handle:
        response = client.post(
            "/api/one-click/generate",
            data={"project_name": "缺正常样本", "reference_build": "GRCh38"},
            files={"tumor_file": ("t.vcf", handle, "text/plain")},
        )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "BLOCKED"
    assert "Normal" in result["message"]


def test_one_click_upload_without_hla_is_blocked(client, tmp_path):
    header = (
        "##fileformat=VCFv4.2\n"
        "##contig=<ID=chr1,length=248956422>\n"
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS\n"
    )
    tumor = tmp_path / "t.vcf"
    normal = tmp_path / "n.vcf"
    record = "chr1\t1003\t.\tA\tG\t60\tPASS\t.\tGT\t0/1\n"
    tumor.write_text(header + record)
    normal.write_text(header + record)
    with open(tumor, "rb") as tf, open(normal, "rb") as nf:
        response = client.post(
            "/api/one-click/generate",
            data={"project_name": "缺 HLA", "reference_build": "GRCh38"},
            files={
                "tumor_file": ("t.vcf", tf, "text/plain"),
                "normal_file": ("n.vcf", nf, "text/plain"),
            },
        )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "BLOCKED"
    assert "HLA" in result["message"]


def test_blueprint_endpoints(client):
    demo = client.post(
        "/api/one-click/generate", data={"demo": "true", "project_name": "图纸项目"}
    ).json()
    construct_id = demo["construct_id"]

    as_json = client.get(f"/api/constructs/{construct_id}/blueprint").json()
    assert as_json["construct_id"] == construct_id
    assert as_json["segments"]

    svg = client.get(
        f"/api/constructs/{construct_id}/blueprint", params={"format": "svg"}
    )
    assert svg.status_code == 200
    assert "svg" in svg.headers["content-type"]
    assert "<svg" in svg.text

    html = client.get(
        f"/api/constructs/{construct_id}/blueprint", params={"format": "html"}
    )
    assert html.status_code == 200
    assert "mRNA vaccine blueprint" in html.text

    pdf = client.get(
        f"/api/constructs/{construct_id}/blueprint", params={"format": "pdf"}
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:5] == b"%PDF-"


def test_one_click_can_target_existing_project(client):
    project = client.post(
        "/api/projects", json={"name": "一键目标项目", "patient_name": "合成患者"}
    ).json()
    response = client.post(
        "/api/one-click/generate",
        data={"demo": "true", "project_id": project["id"], "project_name": "ignored-name"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["project_id"] == project["id"]

    runs = client.get(
        "/api/analysis-runs", params={"project_id": project["id"]}
    ).json()
    assert len(runs) == 1


def test_one_click_unknown_project_is_rejected(client):
    response = client.post(
        "/api/one-click/generate",
        data={"demo": "true", "project_id": "does-not-exist"},
    )
    assert response.status_code == 400


def test_one_click_stage_details_are_populated(client):
    result = client.post(
        "/api/one-click/generate", data={"demo": "true", "project_name": "阶段产出"}
    ).json()
    assert result["status"] == "SUCCESS"
    stages = {s["step"]: s for s in result["stages"]}
    qc = stages["VCF_QC"]["detail"]
    assert qc and "raw" in qc and "valid" in qc and "tumour-only" in qc
    assert stages["ANNOTATION"]["detail"]
    assert stages["CONSTRUCT"]["detail"]
    assert stages["REPORT"]["detail"]
