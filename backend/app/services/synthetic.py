"""Synthetic tumor/normal VCF dataset for demo and automated testing.

The dataset is deliberately small and deterministic. It contains shared
variants with different allele frequencies, tumor-only variants, a normal-only
variant, a weak-evidence (uncertain) variant, a duplicate record, an invalid
allele and a malformed record.
"""
from __future__ import annotations

import gzip
from dataclasses import dataclass
from pathlib import Path

from app.core.reference import GRCH38

TUMOR_VCF = "\n".join(
    [
        "##fileformat=VCFv4.2",
        f"##reference={GRCH38}",
        "##contig=<ID=chr1,length=248956422>",
        "##contig=<ID=chr2,length=242193529>",
        "##contig=<ID=chr3,length=198295559>",
        "##contig=<ID=chr4,length=190214555>",
        "##contig=<ID=chr5,length=181538259>",
        "##contig=<ID=chr6,length=170805979>",
        '##FILTER=<ID=PASS,Description="All filters passed">',
        '##INFO=<ID=DP,Number=1,Type=Integer,Description="Total depth">',
        '##INFO=<ID=AF,Number=A,Type=Float,Description="Allele frequency">',
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">',
        '##FORMAT=<ID=AD,Number=R,Type=Integer,Description="Allelic depths">',
        '##FORMAT=<ID=AF,Number=A,Type=Float,Description="Allele frequency">',
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSYNTHETIC_TUMOR",
        # shared variants (different allele frequencies vs normal)
        "chr1\t1000\t.\tA\tG\t60\tPASS\tDP=60;AF=0.35\tGT:DP:AD:AF\t0/1:60:39,21:0.35",
        "chr1\t2000\t.\tC\tT\t55\tPASS\tDP=48;AF=0.42\tGT:DP:AD:AF\t0/1:48:28,20:0.42",
        "chr2\t3000\t.\tG\tA\t58\tPASS\tDP=52;AF=0.28\tGT:DP:AD:AF\t0/1:52:37,15:0.28",
        # tentative shared but weak normal evidence -> UNCERTAIN
        "chr6\t9000\t.\tG\tT\t62\tPASS\tDP=50;AF=0.40\tGT:DP:AD:AF\t0/1:50:30,20:0.40",
        # tumor-only variants
        "chr3\t4000\t.\tA\tT\t45\tPASS\tDP=40;AF=0.30\tGT:DP:AD:AF\t0/1:40:28,12:0.30",
        "chr3\t4500\t.\tG\tC\t47\tPASS\tDP=38;AF=0.26\tGT:DP:AD:AF\t0/1:38:28,10:0.26",
        "chr4\t6000\t.\tC\tA\t51\tPASS\tDP=44;AF=0.34\tGT:DP:AD:AF\t0/1:44:29,15:0.34",
        # duplicate of chr3:4000
        "chr3\t4000\t.\tA\tT\t45\tPASS\tDP=40;AF=0.30\tGT:DP:AD:AF\t0/1:40:28,12:0.30",
        # invalid allele (symbolic)
        "chr5\t8000\t.\tA\t<DEL>\t30\tPASS\tDP=10\tGT:DP\t0/1:10",
        # malformed record (too few columns)
        "chr1\t7000\t.\tA",
    ]
) + "\n"

NORMAL_VCF = "\n".join(
    [
        "##fileformat=VCFv4.2",
        f"##reference={GRCH38}",
        "##contig=<ID=1,length=248956422>",
        "##contig=<ID=chr1,length=248956422>",
        "##contig=<ID=chr2,length=242193529>",
        "##contig=<ID=chr6,length=170805979>",
        '##FILTER=<ID=PASS,Description="All filters passed">',
        '##INFO=<ID=DP,Number=1,Type=Integer,Description="Total depth">',
        '##INFO=<ID=AF,Number=A,Type=Float,Description="Allele frequency">',
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">',
        '##FORMAT=<ID=AD,Number=R,Type=Integer,Description="Allelic depths">',
        '##FORMAT=<ID=AF,Number=A,Type=Float,Description="Allele frequency">',
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSYNTHETIC_NORMAL",
        # shared variants (Unp refixed chromosome exercises normalisation)
        "1\t1000\t.\tA\tG\t60\tPASS\tDP=55;AF=0.05\tGT:DP:AD:AF\t0/1:55:52,3:0.05",
        "chr1\t2000\t.\tC\tT\t55\tPASS\tDP=50;AF=0.08\tGT:DP:AD:AF\t0/1:50:46,4:0.08",
        "chr2\t3000\t.\tG\tA\t58\tPASS\tDP=60;AF=0.05\tGT:DP:AD:AF\t0/1:60:57,3:0.05",
        # normal-only variant
        "chr1\t5000\t.\tT\tC\t50\tPASS\tDP=45;AF=0.20\tGT:DP:AD:AF\t0/1:45:36,9:0.20",
        # weak evidence -> UNCERTAIN
        "chr6\t9000\t.\tG\tT\t40\tPASS\tDP=3;AF=0.10\tGT:DP:AD:AF\t0/1:3:2,1:0.10",
    ]
) + "\n"


@dataclass
class SyntheticDataset:
    tumor_path: str
    normal_path: str
    reference_build: str
    expected: dict


EXPECTED_SYNTHETIC = {
    "reference_build": GRCH38,
    "tumor": {
        "raw_variants": 10,
        "valid_variants": 8,
        "invalid_variants": 2,
        "duplicate_variants": 1,
        "unique_variants": 7,
        "malformed_records": 1,
    },
    "normal": {
        "raw_variants": 5,
        "valid_variants": 5,
        "invalid_variants": 0,
        "duplicate_variants": 0,
        "unique_variants": 5,
        "malformed_records": 0,
    },
    "somatic": {"TUMOR_ONLY": 3, "NORMAL_ONLY": 1, "SHARED": 3, "UNCERTAIN": 1},
}


def generate_synthetic_dataset(directory: str | Path) -> SyntheticDataset:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    tumor_path = directory / "synthetic_tumor.vcf.gz"
    normal_path = directory / "synthetic_normal.vcf"

    with gzip.open(tumor_path, "wt") as handle:
        handle.write(TUMOR_VCF)
    normal_path.write_text(NORMAL_VCF)

    return SyntheticDataset(
        tumor_path=str(tumor_path),
        normal_path=str(normal_path),
        reference_build=GRCH38,
        expected=EXPECTED_SYNTHETIC,
    )
