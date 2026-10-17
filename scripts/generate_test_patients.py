#!/usr/bin/env python3
"""Generate high-fidelity synthetic patient datasets (a-j) for the platform.

Each patient gets a paired tumour/normal VCF, HLA typing and an expression
profile. The data is fully synthetic (research simulation) and is designed to
run end-to-end through the Bravo platform: VCF -> QC -> annotation -> HLA ->
expression -> candidates -> MHCflurry -> ranking -> report.

Variants include both on-transcript variants (which produce neoantigen
candidates) and realistic cancer-gene coordinates (TP53/KRAS/EGFR/...) that the
platform's mock annotator reports as unknown.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date
from pathlib import Path

OUT_ROOT = Path.home() / "Desktop" / "Bravo_testdata"

CONTIGS = [(f"chr{i}", length) for i, length in zip(
    range(1, 23),
    [248956422, 242193529, 198295559, 190214555, 181538259, 170805979,
     159345973, 145138636, 138394717, 133797422, 135086622, 133275309,
     114364328, 107043718, 101991189, 90338345, 83257441, 80373285,
     58617616, 64444167, 46709983, 50818468],
)] + [("chrX", 156040895), ("chrY", 57227415), ("chrM", 16569)]

HLA_POOL_I = [
    "HLA-A*02:01", "HLA-A*01:01", "HLA-A*03:01", "HLA-A*11:01", "HLA-A*24:02",
    "HLA-A*26:01", "HLA-A*32:01", "HLA-B*07:02", "HLA-B*08:01", "HLA-B*35:01",
    "HLA-B*15:01", "HLA-B*40:01", "HLA-B*44:02", "HLA-C*07:02", "HLA-C*04:01",
    "HLA-C*05:01", "HLA-C*06:02", "HLA-C*03:03",
]
HLA_POOL_II = [
    "HLA-DRB1*15:01", "HLA-DRB1*03:01", "HLA-DRB1*07:01",
    "HLA-DQB1*06:02", "HLA-DQB1*02:01", "HLA-DPB1*04:01",
]

# On-transcript variants (the platform's mock transcripts MOCKGENE1 / MOCKGENE2
# at chr1:1000-1100 and chr2:5000-5100) -> produce real neoantigen candidates.
ON_TARGET = {
    "chr1:1003 A>G": ("chr1", 1003, "A", "G", "missense", "p.K2E"),
    "chr1:1008 G>A": ("chr1", 1008, "G", "A", "synonymous", "p.G3G"),
    "chr1:1009 T>A": ("chr1", 1009, "T", "A", "missense", "p.F4I"),
    "chr1:1012 C>A": ("chr1", 1012, "C", "A", "missense", "p.P5T"),
    "chr2:5003 C>T": ("chr2", 5003, "C", "T", "missense", "p.P2S"),
    "chr2:5006 G>A": ("chr2", 5006, "G", "A", "missense", "p.G3R"),
    "chr1:1003 A>T": ("chr1", 1003, "A", "T", "stop_gained", "p.K2*"),
    "chr1:1004 A>AAA": ("chr1", 1004, "A", "AAA", "frameshift", None),
}

# Realistic cancer-gene coordinates (GRCh38) -> mock annotator reports unknown.
REAL_GENES = [
    ("chr17", 7676154, "C", "T", "TP53"),
    ("chr12", 25245350, "C", "T", "KRAS"),
    ("chr7", 55191822, "T", "A", "EGFR"),
    ("chr17", 43071077, "A", "G", "BRCA1"),
    ("chr3", 179218294, "A", "G", "PIK3CA"),
    ("chr10", 87863438, "C", "T", "PTEN"),
    ("chr13", 32339267, "C", "T", "BRCA2"),
]

EXPRESSION = [
    ("ENSG_MOCK00001.3", "MOCKGENE1", "ENST_MOCK00001.1", "TRANSCRIPT", 10.0),
    ("ENSG_MOCK00002", "MOCKGENE2", "ENST_MOCK00002.1", "TRANSCRIPT", 8.0),
    ("ENSG00000141510.17", "TP53", "", "GENE", 22.0),
    ("ENSG00000133703.12", "KRAS", "", "GENE", 16.0),
    ("ENSG00000146648.19", "EGFR", "ENST00000275493.7", "TRANSCRIPT", 12.0),
    ("ENSG00000012048.23", "BRCA1", "", "GENE", 6.5),
    ("ENSG00000121879.4", "PIK3CA", "", "GENE", 9.4),
    ("ENSG00000171862.11", "PTEN", "", "GENE", 7.1),
    ("ENSG00000139618.16", "BRCA2", "", "GENE", 5.8),
    ("ENSG00000091831.22", "ESR1", "", "GENE", 14.3),
]


def seed_for(letter: str) -> int:
    return int(hashlib.sha256(f"bravo-{letter}".encode()).hexdigest()[:8], 16)


def header(sample: str) -> str:
    lines = ["##fileformat=VCFv4.2", f"##fileDate={date.today():%Y%m%d}", "##reference=GRCh38"]
    for name, length in CONTIGS:
        lines.append(f"##contig=<ID={name},length={length}>")
    lines += [
        '##FILTER=<ID=PASS,Description="All filters passed">',
        '##FILTER=<ID=LowQual,Description="Low quality">',
        '##INFO=<ID=DP,Number=1,Type=Integer,Description="Total depth">',
        '##INFO=<ID=AF,Number=A,Type=Float,Description="Allele frequency">',
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        '##FORMAT=<ID=AD,Number=R,Type=Integer,Description="Allelic depths">',
        '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">',
        '##FORMAT=<ID=AF,Number=A,Type=Float,Description="Allele frequency">',
        f"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{sample}",
    ]
    return "\n".join(lines) + "\n"


def record(chrom, pos, ref, alt, af, dp, rng, qual=None, filt="PASS"):
    alt_count = max(1, round(dp * af))
    ref_count = max(0, dp - alt_count)
    af = round(alt_count / dp, 3)
    if qual is None:
        qual = round(rng.uniform(35, 95), 1)
    return (
        f"{chrom}\t{pos}\t.\t{ref}\t{alt}\t{qual}\t{filt}\tDP={dp};AF={af}\t"
        f"GT:AD:DP:AF\t0/1:{ref_count},{alt_count}:{dp}:{af}"
    )


def build_patient(letter: str) -> dict:
    rng = random.Random(seed_for(letter))
    sample_t = f"patient_{letter}_T"
    sample_n = f"patient_{letter}_N"

    # ---- HLA: 6 Class I + 2 Class II (deterministic per patient) -------------
    i_alleles = rng.sample(HLA_POOL_I, 6)
    ii_alleles = rng.sample(HLA_POOL_II, 2)
    hla_rows = [
        (allele, "I", "synthetic-typing", "mock-typing", round(rng.uniform(0.90, 0.995), 3), "1.0.0")
        for allele in i_alleles
    ] + [
        (allele, "II", "synthetic-typing", "mock-typing", round(rng.uniform(0.85, 0.98), 3), "1.0.0")
        for allele in ii_alleles
    ]

    # ---- Variants ----------------------------------------------------------
    shared = []
    # germline shared: two realistic genes + two on-target (K2E missense + G3G syn)
    for chrom, pos, ref, alt, _gene in [REAL_GENES[0], REAL_GENES[3]]:
        shared.append((chrom, pos, ref, alt, rng.uniform(0.42, 0.55), rng.randint(28, 60)))
    shared.append(("chr1", 1003, "A", "G", rng.uniform(0.05, 0.12), rng.randint(30, 60)))
    shared.append(("chr1", 1008, "G", "A", rng.uniform(0.05, 0.12), rng.randint(30, 60)))

    tumor_only = [
        ("chr2", 5003, "C", "T", rng.uniform(0.20, 0.45), rng.randint(35, 80)),
        ("chr1", 1009, "T", "A", rng.uniform(0.18, 0.40), rng.randint(35, 80)),
        ("chr1", 1012, "C", "A", rng.uniform(0.15, 0.38), rng.randint(35, 80)),
        ("chr2", 5006, "G", "A", rng.uniform(0.18, 0.42), rng.randint(35, 80)),
        ("chr12", 25245350, "C", "T", rng.uniform(0.15, 0.40), rng.randint(35, 90)),  # KRAS
        ("chr7", 55191822, "T", "A", rng.uniform(0.12, 0.35), rng.randint(30, 80)),   # EGFR
    ]
    # patient-specific extras to vary candidate counts
    extras = rng.sample(
        [("chr1", 1003, "A", "T"), ("chr1", 1004, "A", "AAA"), ("chr3", 179218294, "A", "G")],
        k=rng.randint(1, 2),
    )
    for chrom, pos, ref, alt in extras:
        tumor_only.append((chrom, pos, ref, alt, rng.uniform(0.18, 0.45), rng.randint(35, 85)))

    def emit(rows):
        return "\n".join(
            record(c, p, r, a, af, dp, rng) for c, p, r, a, af, dp in rows
        )

    tumor_body = emit(shared + tumor_only)
    normal_body = emit(shared)

    # ---- Files -------------------------------------------------------------
    patient_dir = OUT_ROOT / f"patient_{letter}"
    patient_dir.mkdir(parents=True, exist_ok=True)

    (patient_dir / f"patient_{letter}_tumor.vcf").write_text(header(sample_t) + tumor_body + "\n")
    (patient_dir / f"patient_{letter}_normal.vcf").write_text(header(sample_n) + normal_body + "\n")

    hla_lines = ["allele\tclass\tsource\tmethod\tconfidence\tversion"]
    hla_lines += ["\t".join(str(v) for v in row) for row in hla_rows]
    (patient_dir / f"patient_{letter}_hla.tsv").write_text("\n".join(hla_lines) + "\n")

    expr_lines = ["gene_id\tgene_symbol\ttranscript_id\texpression_value\tunit\tsource\tlevel"]
    for gid, sym, tid, level, base in EXPRESSION:
        value = round(base * rng.uniform(0.6, 1.6), 2)
        expr_lines.append(f"{gid}\t{sym}\t{tid}\t{value}\tTPM\tsynthetic\t{level}")
    (patient_dir / f"patient_{letter}_expression.tsv").write_text("\n".join(expr_lines) + "\n")

    return {
        "patient": f"patient_{letter}",
        "dir": str(patient_dir),
        "tumor_variants": len(shared) + len(tumor_only),
        "normal_variants": len(shared),
        "class_i": len(i_alleles),
        "class_ii": len(ii_alleles),
        "hla": ", ".join(i_alleles + ii_alleles),
    }


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for letter in "abcdefghij":
        manifest.append(build_patient(letter))

    lines = ["patient,tumor_variants,normal_variants,class_i,class_ii,hla"]
    lines += [
        f'{m["patient"]},{m["tumor_variants"]},{m["normal_variants"]},{m["class_i"]},{m["class_ii"]},"{m["hla"]}"'
        for m in manifest
    ]
    (OUT_ROOT / "manifest.csv").write_text("\n".join(lines) + "\n")

    (OUT_ROOT / "README.md").write_text(
        "# Bravo 合成测试患者数据（patient_a … patient_j）\n\n"
        "> 研究模拟数据：完全合成，非真实患者数据，不用于临床或人体。\n\n"
        "每位患者目录 `patient_x/` 包含：\n"
        "- `patient_x_tumor.vcf` / `patient_x_normal.vcf`（GRCh38，配对）\n"
        "- `patient_x_hla.tsv`（I 类 6 个 + II 类 2 个等位基因）\n"
        "- `patient_x_expression.tsv`（TPM，含基因/转录本层级）\n\n"
        "## 使用\n"
        "在「一键生成」页面上传该患者的 tumour/normal VCF、HLA 与表达谱文件，"
        "选择预测提供方（MHCflurry 或 mock）即可自动生成 mRNA 图纸与报告。\n\n"
        "## 说明\n"
        "数据包含两类变异：\n"
        "- 平台 mock 转录本上的变异（MOCKGENE1/MOCKGENE2），会产生真实的新抗原候选；\n"
        "- 真实癌症基因坐标（TP53/KRAS/EGFR/BRCA1…），平台的 mock 注释器会报告为 unknown。\n"
    )
    print(f"Wrote {len(manifest)} patients to {OUT_ROOT}")
    for m in manifest:
        print(" ", m["patient"], m["dir"])


if __name__ == "__main__":
    main()
