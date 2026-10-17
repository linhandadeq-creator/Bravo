"""Synthetic HLA + expression data linked to the Phase 3 synthetic variants.

Expression covers ``MOCKGENE1`` and ``MOCKGENE2`` — the mock transcripts used by
``MockVariantAnnotator`` — so the integrated dataset demonstrates the full
Variant + Annotation + HLA + Expression chain.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.reference import GRCH38

SYNTHETIC_HLA = [
    {"allele": "HLA-A*02:01", "class": "I", "source": "synthetic", "method": "mock-typing", "confidence": 0.99, "version": "1.0.0"},
    {"allele": "HLA-A*01:01", "class": "I", "source": "synthetic", "method": "mock-typing", "confidence": 0.97, "version": "1.0.0"},
    {"allele": "HLA-B*07:02", "class": "I", "source": "synthetic", "method": "mock-typing", "confidence": 0.95, "version": "1.0.0"},
    {"allele": "HLA-C*07:02", "class": "I", "source": "synthetic", "method": "mock-typing", "confidence": 0.93, "version": "1.0.0"},
    {"allele": "HLA-DRB1*15:01", "class": "II", "source": "synthetic", "method": "mock-typing", "confidence": 0.90, "version": "1.0.0"},
    {"allele": "HLA-DQB1*06:02", "class": "II", "source": "synthetic", "method": "mock-typing", "confidence": 0.88, "version": "1.0.0"},
]

SYNTHETIC_EXPRESSION = [
    {"gene_id": "ENSG_MOCK00001.3", "gene_symbol": "MOCKGENE1", "transcript_id": "ENST_MOCK00001.1", "expression_value": 12.5, "unit": "TPM", "source": "synthetic", "level": "TRANSCRIPT"},
    {"gene_id": "ENSG_MOCK00002", "gene_symbol": "MOCKGENE2", "transcript_id": "ENST_MOCK00002.1", "expression_value": 8.2, "unit": "TPM", "source": "synthetic", "level": "TRANSCRIPT"},
    {"gene_id": "ENSG00000141510", "gene_symbol": "TP53", "expression_value": 20.1, "unit": "TPM", "source": "synthetic", "level": "GENE"},
    {"gene_id": "ENSG00000133703", "gene_symbol": "KRAS", "expression_value": 15.7, "unit": "TPM", "source": "synthetic", "level": "GENE"},
]

HEADER = [
    "##fileformat=VCFv4.2",
    f"##reference={GRCH38}",
    "##contig=<ID=chr1,length=248956422>",
    "##contig=<ID=chr2,length=242193529>",
    "##contig=<ID=chr9,length=138394717>",
    '##FILTER=<ID=PASS,Description="All filters passed">',
    '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
    '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">',
    '##FORMAT=<ID=AF,Number=A,Type=Float,Description="Allele frequency">',
]

# On-target variants engineered onto the mock transcripts:
# chr1:1003 -> MOCKGENE1 missense, chr1:1008 -> MOCKGENE1 synonymous,
# chr2:5003 -> MOCKGENE2 missense, chr9:12345 -> intergenic.
#
# The tumour carries somatic (tumour-only) drivers; the normal carries only the
# benign germline variants (the synonymous and intergenic ones). The two samples
# must differ — otherwise every "somatic" call is really germline.
TUMOR_RECORDS = [
    "chr1\t1003\t.\tA\tG\t60\tPASS\t.\tGT:DP:AF\t0/1:40:0.35",
    "chr1\t1008\t.\tG\tA\t58\tPASS\t.\tGT:DP:AF\t0/1:38:0.30",
    "chr2\t5003\t.\tC\tT\t61\tPASS\t.\tGT:DP:AF\t0/1:45:0.40",
    "chr9\t12345\t.\tA\tG\t55\tPASS\t.\tGT:DP:AF\t0/1:30:0.25",
]
NORMAL_RECORDS = [
    "chr1\t1008\t.\tG\tA\t58\tPASS\t.\tGT:DP:AF\t0/1:38:0.30",
    "chr9\t12345\t.\tA\tG\t55\tPASS\t.\tGT:DP:AF\t0/1:30:0.25",
]


@dataclass
class SyntheticIntegration:
    tumor_path: str
    normal_path: str
    hla_path: str
    expression_path: str
    reference_build: str
    expected_genes: list[str]
    expected_hla_status: str
    expected_expression_status: str


def _write_vcf(path: Path, sample_name: str, records: list[str]) -> None:
    content = "\n".join(HEADER)
    content += f"\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{sample_name}\n"
    content += "\n".join(records) + "\n"
    path.write_text(content)


def generate_synthetic_integration(directory: str | Path) -> SyntheticIntegration:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    tumor_path = directory / "integration_tumor.vcf"
    normal_path = directory / "integration_normal.vcf"
    hla_path = directory / "synthetic_hla.json"
    expression_path = directory / "synthetic_expression.tsv"

    _write_vcf(tumor_path, "TUMOR", TUMOR_RECORDS)
    _write_vcf(normal_path, "NORMAL", NORMAL_RECORDS)

    hla_path.write_text(json.dumps({"alleles": SYNTHETIC_HLA}, indent=2))

    lines = ["gene_id\tgene_symbol\ttranscript_id\texpression_value\tunit\tsource\tlevel"]
    for row in SYNTHETIC_EXPRESSION:
        lines.append(
            "\t".join(
                str(row.get(field) or "")
                for field in (
                    "gene_id",
                    "gene_symbol",
                    "transcript_id",
                    "expression_value",
                    "unit",
                    "source",
                    "level",
                )
            )
        )
    expression_path.write_text("\n".join(lines) + "\n")

    return SyntheticIntegration(
        tumor_path=str(tumor_path),
        normal_path=str(normal_path),
        hla_path=str(hla_path),
        expression_path=str(expression_path),
        reference_build=GRCH38,
        expected_genes=["MOCKGENE1", "MOCKGENE2"],
        expected_hla_status="HLA_AVAILABLE",
        expected_expression_status="EXPRESSION_AVAILABLE",
    )
