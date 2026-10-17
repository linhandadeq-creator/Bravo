HEADER = "\n".join(
    [
        "##fileformat=VCFv4.2",
        "##reference=GRCh38",
        "##contig=<ID=chr1,length=248956422>",
        "##contig=<ID=chr2,length=242193529>",
        "##contig=<ID=chr9,length=138394717>",
        '##FILTER=<ID=PASS,Description="All filters passed">',
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">',
        '##FORMAT=<ID=AF,Number=A,Type=Float,Description="Allele frequency">',
    ]
)

RECORDS = [
    "chr1\t1003\t.\tA\tG\t60\tPASS\t.\tGT:DP:AF\t0/1:30:0.30",
    "chr1\t1008\t.\tG\tA\t60\tPASS\t.\tGT:DP:AF\t0/1:30:0.30",
    "chr2\t5040\t.\tA\tG\t60\tPASS\t.\tGT:DP:AF\t0/1:30:0.30",
    "chr9\t12345\t.\tA\tG\t60\tPASS\t.\tGT:DP:AF\t0/1:30:0.30",
]


def _write_vcf(path, sample_name: str) -> None:
    content = HEADER + f"\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{sample_name}\n"
    content += "\n".join(RECORDS) + "\n"
    path.write_text(content)


def _create_project(client, name="Annotation Project") -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _setup_run(client, tmp_path, name="Annotation Project"):
    project_id = _create_project(client, name)
    tumor = tmp_path / "annotation_tumor.vcf"
    normal = tmp_path / "annotation_normal.vcf"
    _write_vcf(tumor, "TUMOR")
    _write_vcf(normal, "NORMAL")
    with open(tumor, "rb") as tf, open(normal, "rb") as nf:
        response = client.post(
            "/api/analysis-runs/upload",
            data={"project_id": project_id, "reference_build": "GRCh38"},
            files={
                "tumor_file": ("annotation_tumor.vcf", tf, "text/plain"),
                "normal_file": ("annotation_normal.vcf", nf, "text/plain"),
            },
        )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "PASS", run.get("error_message")
    return project_id, run["id"]


def test_providers_list(client):
    providers = client.get("/api/annotation/providers").json()
    by_name = {p["name"]: p for p in providers}
    assert by_name["mock"]["available"] is True
    assert by_name["mock"]["reference_build"] == "GRCh38"
    # VEP is a real REST provider (availability depends on network).
    assert by_name["vep"]["provider_version"] == "REST"
    for stub in ("snpeff", "annovar"):
        assert by_name[stub]["available"] is False


def test_annotate_run_and_provenance(client, tmp_path):
    _, run_id = _setup_run(client, tmp_path)

    response = client.post(
        f"/api/analysis-runs/{run_id}/annotate", json={"provider": "mock"}
    )
    assert response.status_code == 201
    annotation_run = response.json()
    assert annotation_run["status"] == "PARTIAL"
    assert annotation_run["partial_count"] == 2
    assert annotation_run["failed_count"] == 0
    assert annotation_run["reference_build"] == "GRCh38"
    assert annotation_run["transcript_source"] == "MockTranscripts"
    assert annotation_run["input_hash"]
    assert annotation_run["compatibility"]["ok"] is True

    annotations = client.get(f"/api/analysis-runs/{run_id}/annotations").json()
    assert len(annotations) == 8
    sample = next(
        a
        for a in annotations
        if a["gene"] == "MOCKGENE1" and a["consequence"] == "missense"
    )
    assert sample["protein_change"] == "p.K2E"
    assert sample["provider"] == "mock"
    assert sample["provider_version"]
    assert sample["annotation_version"]
    assert sample["transcript_source"] == "MockTranscripts"
    assert sample["input_hash"]
    assert sample["annotation_timestamp"]


def test_annotated_variants_filter_override(client, tmp_path):
    _, run_id = _setup_run(client, tmp_path)
    client.post(f"/api/analysis-runs/{run_id}/annotate", json={"provider": "mock"})

    missense = client.get(
        f"/api/analysis-runs/{run_id}/annotated-variants", params={"allowed": "missense"}
    ).json()
    assert len(missense) == 2
    assert {item["consequence"] for item in missense} == {"missense"}

    both = client.get(
        f"/api/analysis-runs/{run_id}/annotated-variants",
        params={"allowed": "missense,synonymous"},
    ).json()
    assert len(both) == 4

    # default project filter is missense, frameshift, stop_gained
    default = client.get(f"/api/analysis-runs/{run_id}/annotated-variants").json()
    assert {item["consequence"] for item in default} == {"missense"}


def test_filter_config_roundtrip(client):
    project_id = _create_project(client, "Filter Project")

    default = client.get(f"/api/projects/{project_id}/annotation-filter").json()
    assert "missense" in default["allowed_consequences"]

    updated = client.put(
        f"/api/projects/{project_id}/annotation-filter",
        json={"allowed_consequences": ["synonymous", "missense"]},
    ).json()
    assert updated["allowed_consequences"] == ["synonymous", "missense"]

    fetched = client.get(f"/api/projects/{project_id}/annotation-filter").json()
    assert fetched["allowed_consequences"] == ["synonymous", "missense"]

    invalid = client.put(
        f"/api/projects/{project_id}/annotation-filter",
        json={"allowed_consequences": ["not_a_consequence"]},
    )
    assert invalid.status_code == 400


def test_annotated_variants_respect_project_config(client, tmp_path):
    project_id, run_id = _setup_run(client, tmp_path)
    client.post(f"/api/analysis-runs/{run_id}/annotate", json={"provider": "mock"})

    client.put(
        f"/api/projects/{project_id}/annotation-filter",
        json={"allowed_consequences": ["synonymous"]},
    )
    filtered = client.get(f"/api/analysis-runs/{run_id}/annotated-variants").json()
    assert {item["consequence"] for item in filtered} == {"synonymous"}
    assert len(filtered) == 2


def test_neoantigen_gate_blocks_without_annotation(client, tmp_path):
    project_id = _create_project(client, "Gate Project")
    run = client.post(
        "/api/analysis-runs/synthetic", json={"project_id": project_id}
    ).json()

    response = client.get(f"/api/analysis-runs/{run['id']}/neoantigen-input")
    assert response.status_code == 409
    assert "annotation" in response.json()["detail"].lower()


def test_neoantigen_gate_allows_annotated_tumor_variants(client, tmp_path):
    _, run_id = _setup_run(client, tmp_path)
    client.post(f"/api/analysis-runs/{run_id}/annotate", json={"provider": "mock"})

    allowed = client.get(f"/api/analysis-runs/{run_id}/neoantigen-input").json()
    assert allowed
    assert all(item["sample_role"] == "TUMOR" for item in allowed)
    # default allowed = missense/frameshift/stop_gained
    assert {item["consequence"] for item in allowed} == {"missense"}
    assert allowed[0]["protein_change"] == "p.K2E"


def test_neoantigen_gate_blocks_non_pass_run(client, tmp_path):
    project_id = _create_project(client, "Blocked Gate Project")
    tumor = tmp_path / "blocked_tumor.vcf"
    _write_vcf(tumor, "TUMOR")
    with open(tumor, "rb") as tf:
        run = client.post(
            "/api/analysis-runs/upload",
            data={"project_id": project_id, "reference_build": "GRCh38"},
            files={"tumor_file": ("blocked_tumor.vcf", tf, "text/plain")},
        ).json()
    assert run["status"] == "BLOCKED"

    client.post(f"/api/analysis-runs/{run['id']}/annotate", json={"provider": "mock"})

    gate = client.get(f"/api/analysis-runs/{run['id']}/neoantigen-input")
    assert gate.status_code == 409
    assert "PASS" in gate.json()["detail"]


def test_unavailable_provider_is_reported(client, tmp_path):
    _, run_id = _setup_run(client, tmp_path)

    # snpeff/annovar are reserved (unavailable). vep is a real REST provider.
    response = client.post(
        f"/api/analysis-runs/{run_id}/annotate", json={"provider": "snpeff"}
    )
    assert response.status_code == 201
    assert response.json()["status"] == "UNAVAILABLE"

    gate = client.get(f"/api/analysis-runs/{run_id}/neoantigen-input")
    assert gate.status_code == 409


def test_variant_detail_includes_evidence_and_annotation(client, tmp_path):
    _, run_id = _setup_run(client, tmp_path)
    client.post(f"/api/analysis-runs/{run_id}/annotate", json={"provider": "mock"})

    variants = client.get(
        f"/api/analysis-runs/{run_id}/variants", params={"role": "TUMOR"}
    ).json()
    target = next(v for v in variants if v["position"] == 1003)

    detail = client.get(
        f"/api/analysis-runs/{run_id}/variants/{target['id']}"
    ).json()
    assert detail["variant"]["id"] == target["id"]
    assert detail["tumor_evidence"] is not None
    assert detail["normal_evidence"] is not None
    assert detail["annotation"]["protein_change"] == "p.K2E"
    assert detail["annotation_run"]["provider"] == "mock"
