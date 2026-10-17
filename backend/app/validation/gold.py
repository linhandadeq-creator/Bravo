"""Synthetic gold dataset with expected scientific results.

Everything here is deterministic and synthetic. The expected values encode the
scientific outcome the platform must reproduce.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.reference import GRCH38

HEADER = "\n".join(
    [
        "##fileformat=VCFv4.2",
        f"##reference={GRCH38}",
        "##contig=<ID=chr1,length=248956422>",
        "##contig=<ID=chr2,length=242193529>",
        "##contig=<ID=chr3,length=198295559>",
        '##FILTER=<ID=PASS,Description="All filters passed">',
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">',
        '##FORMAT=<ID=AD,Number=R,Type=Integer,Description="Allelic depths">',
        '##FORMAT=<ID=AF,Number=A,Type=Float,Description="Allele frequency">',
    ]
)

# chr1:1003 -> MOCKGENE1 missense p.K2E
# chr1:1008 -> MOCKGENE1 synonymous p.G3G
# chr2:5003 -> MOCKGENE2 missense p.P2S
# chr3:4000 -> intergenic (unknown)
GOLD_TUMOR_RECORDS = [
    "chr1\t1003\t.\tA\tG\t60\tPASS\t.\tGT:DP:AD:AF\t0/1:60:39,21:0.35",
    "chr1\t1008\t.\tG\tA\t58\tPASS\t.\tGT:DP:AD:AF\t0/1:50:46,4:0.08",
    "chr2\t5003\t.\tC\tT\t61\tPASS\t.\tGT:DP:AD:AF\t0/1:45:36,9:0.20",
    "chr3\t4000\t.\tA\tT\t45\tPASS\t.\tGT:DP:AD:AF\t0/1:40:30,10:0.25",
]

# Normal carries only the benign germline variant (chr1:1008). The tumour
# drivers (chr1:1003, chr2:5003) and the intergenic chr3:4000 are tumour-only,
# so the germline synonymous variant is the sole SHARED call.
GOLD_NORMAL_RECORDS = [
    "chr1\t1008\t.\tG\tA\t58\tPASS\t.\tGT:DP:AD:AF\t0/1:50:47,3:0.06",
]

GOLD_HLA = [
    {"allele": "HLA-A*02:01", "class": "I"},
    {"allele": "HLA-A*01:01", "class": "I"},
    {"allele": "HLA-B*07:02", "class": "I"},
    {"allele": "HLA-C*07:02", "class": "I"},
    {"allele": "HLA-DRB1*15:01", "class": "II"},
    {"allele": "HLA-DQB1*06:02", "class": "II"},
]

GOLD_EXPRESSION = (
    "gene_id\tgene_symbol\ttranscript_id\texpression_value\tunit\tsource\tlevel\n"
    "ENSG_MOCK00001.3\tMOCKGENE1\tENST_MOCK00001.1\t12.5\tTPM\tgold\tTRANSCRIPT\n"
    "ENSG_MOCK00002\tMOCKGENE2\tENST_MOCK00002.1\t8.2\tTPM\tgold\tTRANSCRIPT\n"
    "ENSG00000141510\tTP53\t\t20.1\tTPM\tgold\tGENE\n"
)

EXPECTED = {
    "reference_build": GRCH38,
    "qc": {
        "status": "PASS",
        "tumor_raw": 4,
        "normal_raw": 1,
        "invalid": 0,
        "malformed": 0,
        "duplicate": 0,
    },
    "somatic": {"TUMOR_ONLY": 3, "NORMAL_ONLY": 0, "SHARED": 1, "UNCERTAIN": 0},
    "annotation": [
        {"chromosome": "chr1", "position": 1003, "consequence": "missense", "gene": "MOCKGENE1", "protein_change": "p.K2E"},
        {"chromosome": "chr1", "position": 1008, "consequence": "synonymous", "gene": "MOCKGENE1", "protein_change": "p.G3G"},
        {"chromosome": "chr2", "position": 5003, "consequence": "missense", "gene": "MOCKGENE2", "protein_change": "p.P2S"},
        {"chromosome": "chr3", "position": 4000, "consequence": "unknown", "gene": None, "protein_change": None},
    ],
    "hla": {"status": "HLA_AVAILABLE", "valid": 6, "invalid": 0, "duplicate": 0, "class_i": 4, "class_ii": 2},
    "expression": {"status": "EXPRESSION_AVAILABLE", "valid": 3, "gene_level": 1, "transcript_level": 2, "mapped_genes": ["MOCKGENE1", "MOCKGENE2", "TP53"]},
    "neoantigen": {"total": 24, "generated": 12, "rejected": 12, "ranked": 12, "prediction_status": "MOCK", "protein_changes": ["p.K2E", "p.P2S"]},
    "ranking": {"weight_sum": 1.0, "score_min": 0.0, "score_max": 100.0},
    "construct": {
        "candidates": 2,
        "representation": "[5PRIME] [ANTIGEN_001] [SPACER] [ANTIGEN_002] [3PRIME]",
        "status": "VALIDATED_SIMULATION",
        "labels": ["ANTIGEN_001", "ANTIGEN_002"],
    },
}

GOLD_DATASET_NAME = "Synthetic Gold Dataset v1"


@dataclass
class GoldDataset:
    directory: str
    tumor_path: str
    normal_path: str
    hla_content: str
    expression_content: str
    reference_build: str
    expected: dict


def _write_vcf(path: Path, sample_name: str, records: list[str]) -> None:
    content = HEADER
    content += f"\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{sample_name}\n"
    content += "\n".join(records) + "\n"
    path.write_text(content)


def generate_gold_dataset(directory: str | Path) -> GoldDataset:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    tumor_path = directory / "gold_tumor.vcf"
    normal_path = directory / "gold_normal.vcf"
    _write_vcf(tumor_path, "GOLD_TUMOR", GOLD_TUMOR_RECORDS)
    _write_vcf(normal_path, "GOLD_NORMAL", GOLD_NORMAL_RECORDS)
    return GoldDataset(
        directory=str(directory),
        tumor_path=str(tumor_path),
        normal_path=str(normal_path),
        hla_content=json.dumps({"alleles": GOLD_HLA}),
        expression_content=GOLD_EXPRESSION,
        reference_build=GRCH38,
        expected=EXPECTED,
    )
