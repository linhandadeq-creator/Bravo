#!/usr/bin/env python3
"""Generate 50 realistic patient datasets with **real, verified** variants.

Every somatic variant is a documented cancer hotspot (gene + protein change). The
exact GRCh38 chromosome/position/ref/alt is *derived from the real Ensembl
reference* (via the offline annotation index), then round-trip verified with the
offline annotator — so nothing is fabricated. Germline variants are real
synonymous substitutions; HLA alleles are real, weighted by approximate
population frequency; expression values are plausible TPMs for real genes.

Output: ~/Desktop/Bravo_real_patients/patient_001 … patient_050
"""
from __future__ import annotations

import hashlib
import os
import random
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("OFFLINE_REFERENCE_DIR", str(ROOT / "backend" / "storage" / "reference"))
os.environ.setdefault("STORAGE_DIR", str(ROOT / "backend" / "storage"))

from app.annotation.base import ReferenceContext, VariantInput  # noqa: E402
from app.annotation.offline import _load_index, _codon_aa  # noqa: E402
from app.annotation.vep import _translate  # noqa: E402

OUT_ROOT = Path.home() / "Desktop" / "Bravo_real_patients"
BUILD = "GRCh38"
_COMPLEMENT = str.maketrans("ACGT", "TGCA")

CONTIGS = [
    (f"chr{i}", length)
    for i, length in zip(
        range(1, 23),
        [248956422, 242193529, 198295559, 190214555, 181538259, 170805979,
         159345973, 145138636, 138394717, 133797422, 135086622, 133275309,
         114364328, 107043718, 101991189, 90338345, 83257441, 80373285,
         58617616, 64444167, 46709983, 50818468],
    )
] + [("chrX", 156040895), ("chrY", 57227415), ("chrM", 16569)]

# Documented activating / hotspot protein changes (real drivers).
HOTSPOTS: list[tuple[str, str]] = [
    ("BRAF", "p.V600E"), ("BRAF", "p.V600K"), ("BRAF", "p.V600R"),
    ("KRAS", "p.G12D"), ("KRAS", "p.G12V"), ("KRAS", "p.G12C"), ("KRAS", "p.G12A"),
    ("KRAS", "p.G12S"), ("KRAS", "p.G12R"), ("KRAS", "p.G13D"), ("KRAS", "p.G13C"),
    ("KRAS", "p.Q61H"), ("KRAS", "p.Q61R"), ("KRAS", "p.Q61K"), ("KRAS", "p.Q61L"),
    ("NRAS", "p.G12D"), ("NRAS", "p.G12V"), ("NRAS", "p.G12C"), ("NRAS", "p.G12S"),
    ("NRAS", "p.Q61R"), ("NRAS", "p.Q61K"), ("NRAS", "p.Q61L"),
    ("HRAS", "p.G12V"), ("HRAS", "p.G12C"), ("HRAS", "p.G12S"), ("HRAS", "p.Q61R"),
    ("EGFR", "p.L858R"), ("EGFR", "p.L858Q"), ("EGFR", "p.T790M"), ("EGFR", "p.L861Q"),
    ("EGFR", "p.S768I"), ("EGFR", "p.G719S"), ("EGFR", "p.G719A"), ("EGFR", "p.G719C"),
    ("PIK3CA", "p.E545K"), ("PIK3CA", "p.E542K"), ("PIK3CA", "p.H1047R"),
    ("PIK3CA", "p.H1047L"), ("PIK3CA", "p.E545A"), ("PIK3CA", "p.N345K"),
    ("TP53", "p.R175H"), ("TP53", "p.R273H"), ("TP53", "p.R273C"), ("TP53", "p.R248Q"),
    ("TP53", "p.R248W"), ("TP53", "p.Y220C"), ("TP53", "p.G245S"), ("TP53", "p.R282W"),
    ("PTEN", "p.R130Q"), ("PTEN", "p.R130G"), ("PTEN", "p.R173C"), ("PTEN", "p.R233*"),
    ("PTEN", "p.R130*"), ("IDH1", "p.R132H"), ("IDH1", "p.R132C"), ("IDH1", "p.R132G"),
    ("IDH2", "p.R172K"), ("IDH2", "p.R140Q"), ("IDH2", "p.R172M"),
    ("AKT1", "p.E17K"), ("CTNNB1", "p.S33F"), ("CTNNB1", "p.S33Y"), ("CTNNB1", "p.S37F"),
    ("CTNNB1", "p.S45F"), ("CTNNB1", "p.S45P"), ("APC", "p.R1450*"), ("APC", "p.R876*"),
    ("GNAS", "p.R201C"), ("GNAS", "p.R201H"), ("ERBB2", "p.S310F"), ("ERBB2", "p.V842I"),
    ("ERBB2", "p.L755S"), ("SMAD4", "p.R361C"), ("VHL", "p.R167Q"), ("FOXL2", "p.C134W"),
    ("ESR1", "p.Y537S"), ("ESR1", "p.D538G"), ("KRAS", "p.G12F"), ("BRAF", "p.G469A"),
]

GERMLINE_GENES = ["ACTB", "GAPDH", "TP53", "EGFR", "KRAS", "PTEN", "APC", "BRCA1", "BRCA2", "PIK3CA"]

# Real HLA alleles with approximate population frequencies (weights are relative).
HLA_CLASS_I = {
    "A": {"A*02:01": 28, "A*01:01": 15, "A*03:01": 14, "A*11:01": 8, "A*24:02": 9,
          "A*26:01": 4, "A*32:01": 3, "A*23:01": 3, "A*29:02": 3, "A*68:01": 2},
    "B": {"B*07:02": 11, "B*08:01": 10, "B*35:01": 6, "B*15:01": 5, "B*40:01": 6,
          "B*44:02": 8, "B*44:03": 4, "B*13:02": 3, "B*18:01": 3, "B*51:01": 4},
    "C": {"C*07:02": 16, "C*04:01": 9, "C*05:01": 7, "C*06:02": 6, "C*03:03": 6,
          "C*03:04": 8, "C*07:01": 7, "C*08:01": 3},
}
HLA_CLASS_II = {
    "DRB1": {"DRB1*15:01": 13, "DRB1*03:01": 10, "DRB1*07:01": 12,
             "DRB1*04:01": 9, "DRB1*13:01": 6, "DRB1*11:01": 6},
    "DQB1": {"DQB1*06:02": 13, "DQB1*02:01": 12, "DQB1*03:01": 12,
             "DQB1*05:01": 10, "DQB1*03:02": 8},
}

# Housekeeping / common genes for the expression panel (base TPM).
HOUSEKEEPING = {
    "ACTB": 2100.0, "GAPDH": 1600.0, "B2M": 900.0, "TBP": 40.0, "RPL13A": 800.0,
    "TUBB": 350.0, "EEF1A1": 1200.0, "PSMB8": 120.0, "TAP1": 60.0, "HLA-A": 300.0,
}


def _weighted_choice(rng: random.Random, weights: dict[str, int]) -> str:
    items = list(weights.items())
    total = sum(w for _, w in items)
    pick = rng.uniform(0, total)
    upto = 0.0
    for allele, weight in items:
        upto += weight
        if pick <= upto:
            return allele
    return items[-1][0]


def _find_transcript(index, gene: str):
    cands = [
        t for t in index.transcripts
        if t["gene"] == gene and t["biotype"] == "protein_coding"
    ]
    if not cands:
        return None
    mane = [t for t in cands if t["mane"]]
    pool = mane or [t for t in cands if t["canonical"]] or cands
    return max(pool, key=lambda t: sum(e - s + 1 for s, e in t["cds"]))


def _offset_to_genomic(transcript, offset: int) -> int:
    ordered = transcript["cds"] if transcript["strand"] != "-" else list(reversed(transcript["cds"]))
    cum = 0
    for start, end in ordered:
        length = end - start + 1
        if offset < cum + length:
            delta = offset - cum
            return end - delta if transcript["strand"] == "-" else start + delta
        cum += length
    raise ValueError("offset outside CDS")


def make_variant(index, gene: str, protein_change: str):
    """Derive a real GRCh38 SNV from a gene + protein change using the reference."""
    match = re.match(r"^p\.([A-Z*])(\d+)([A-Z*])$", protein_change)
    if not match:
        return None
    ref_letter, position, alt_letter = match.group(1), int(match.group(2)), match.group(3)
    transcript = _find_transcript(index, gene)
    if transcript is None:
        return None
    cds = index.cds_sequence(transcript["tid"])
    if not cds:
        return None
    protein = _translate(cds)
    if position < 1 or position > len(protein) or protein[position - 1] != ref_letter:
        return None
    ref_codon = cds[(position - 1) * 3: (position - 1) * 3 + 3]
    if len(ref_codon) < 3 or _codon_aa(ref_codon) != ref_letter:
        return None
    for base_index in range(3):
        for base in "ACGT":
            if base == ref_codon[base_index]:
                continue
            alt_codon = ref_codon[:base_index] + base + ref_codon[base_index + 1:]
            if _codon_aa(alt_codon) != alt_letter:
                continue
            offset = (position - 1) * 3 + base_index
            genomic = _offset_to_genomic(transcript, offset)
            ref_base, alt_base = ref_codon[base_index], base
            if transcript["strand"] == "-":
                ref_base = ref_base.translate(_COMPLEMENT)
                alt_base = alt_base.translate(_COMPLEMENT)
            return {
                "gene": gene,
                "protein_change": protein_change,
                "chrom": transcript["chrom"],
                "pos": genomic,
                "ref": ref_base,
                "alt": alt_base,
                "transcript": transcript["tid"],
            }
    return None


def make_germline_synonymous(index, gene: str, rng: random.Random):
    transcript = _find_transcript(index, gene)
    if transcript is None:
        return None
    cds = index.cds_sequence(transcript["tid"])
    if not cds:
        return None
    protein = _translate(cds)
    if len(protein) < 5:
        return None
    position = rng.randint(2, len(protein) - 1)
    ref_codon = cds[(position - 1) * 3: (position - 1) * 3 + 3]
    if _codon_aa(ref_codon) != protein[position - 1] or "*" in ref_codon:
        return None
    for base_index in range(3):
        for base in "ACGT":
            if base == ref_codon[base_index]:
                continue
            alt_codon = ref_codon[:base_index] + base + ref_codon[base_index + 1:]
            if _codon_aa(alt_codon) == _codon_aa(ref_codon):
                offset = (position - 1) * 3 + base_index
                genomic = _offset_to_genomic(transcript, offset)
                ref_base, alt_base = ref_codon[base_index], base
                if transcript["strand"] == "-":
                    ref_base = ref_base.translate(_COMPLEMENT)
                    alt_base = alt_base.translate(_COMPLEMENT)
                return {
                    "gene": gene, "protein_change": f"p.{protein[position-1]}{position}=",
                    "chrom": transcript["chrom"], "pos": genomic,
                    "ref": ref_base, "alt": alt_base, "transcript": transcript["tid"],
                }
    return None


def vcf_header(sample: str) -> str:
    lines = ["##fileformat=VCFv4.2", f"##fileDate={date.today():%Y%m%d}", "##reference=GRCh38"]
    lines += [f"##contig=<ID={name},length={length}>" for name, length in CONTIGS]
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


def vcf_record(variant, af, dp, rng, filt="PASS") -> str:
    alt_count = max(1, round(dp * af))
    ref_count = max(0, dp - alt_count)
    af = round(alt_count / dp, 3)
    qual = round(rng.uniform(35, 99), 1)
    return (
        f"{variant['chrom']}\t{variant['pos']}\t.\t{variant['ref']}\t{variant['alt']}\t"
        f"{qual}\t{filt}\tDP={dp};AF={af}\tGT:AD:DP:AF\t0/1:{ref_count},{alt_count}:{dp}:{af}"
    )


def verify(index, variants):
    from app.annotation.offline import OfflineAnnotator

    annotator = OfflineAnnotator(reference_build=BUILD)
    inputs = [
        VariantInput(
            key=f"{v['chrom']}:{v['pos']}:{v['ref']}>{v['alt']}",
            chromosome=v["chrom"], position=v["pos"], reference=v["ref"], alternate=v["alt"],
        )
        for v in variants
    ]
    records = annotator.annotate(inputs, ReferenceContext(reference_build=BUILD))
    problems = []
    for variant, record in zip(variants, records):
        if record.status != "ANNOTATED":
            problems.append((variant, f"status={record.status}"))
        elif record.gene != variant["gene"]:
            problems.append((variant, f"gene={record.gene} != {variant['gene']}"))
        elif record.protein_change != variant["protein_change"]:
            problems.append((variant, f"{record.protein_change} != {variant['protein_change']}"))
    return problems


def main() -> None:
    index = _load_index(BUILD)

    catalog = []
    for gene, change in HOTSPOTS:
        variant = make_variant(index, gene, change)
        if variant:
            catalog.append(variant)
    # keep only variants that round-trip through the real annotator
    problems = verify(index, catalog)
    bad = {id(v) for v, _ in problems}
    catalog = [v for v in catalog if id(v) not in bad]
    print(f"hotspot catalog: {len(catalog)} verified variants (dropped {len(problems)})")
    for variant, reason in problems:
        print("  dropped:", variant["gene"], variant["protein_change"], "->", reason)

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest_rows = ["patient,somatic_variants,germline_variants,class_i,class_ii,genes"]
    verification_rows = ["patient,gene,protein_change,chrom,pos,ref,alt"]
    all_checked = []

    for number in range(1, 51):
        rng = random.Random(int(hashlib.sha256(f"bravo-real-{number}".encode()).hexdigest()[:8], 16))
        name = f"patient_{number:03d}"
        patient_dir = OUT_ROOT / name
        patient_dir.mkdir(parents=True, exist_ok=True)

        n_somatic = rng.randint(5, 14)
        somatic = rng.sample(catalog, n_somatic)

        germline = []
        for gene in rng.sample(GERMLINE_GENES, rng.randint(1, 3)):
            g = make_germline_synonymous(index, gene, rng)
            if g:
                germline.append(g)

        tumor_lines = [vcf_record(v, rng.uniform(0.08, 0.5), rng.randint(30, 95), rng) for v in somatic]
        normal_shared = [vcf_record(v, rng.uniform(0.35, 0.6), rng.randint(25, 60), rng) for v in germline]
        tumor_lines += normal_shared
        rng.shuffle(tumor_lines)

        (patient_dir / f"{name}_tumor.vcf").write_text(
            vcf_header(f"{name}_T") + "\n".join(tumor_lines) + "\n"
        )
        (patient_dir / f"{name}_normal.vcf").write_text(
            vcf_header(f"{name}_N")
            + ("\n".join(normal_shared) + "\n" if normal_shared else "")
        )

        hla_rows = []
        for locus, weights in HLA_CLASS_I.items():
            for allele in rng.sample(list(weights), 2):
                hla_rows.append((allele, "I", "arcasHLA", "sequence-based", round(rng.uniform(0.90, 0.999), 3), "1.0.0"))
        for locus, weights in HLA_CLASS_II.items():
            for allele in rng.sample(list(weights), 1):
                hla_rows.append((allele, "II", "arcasHLA", "sequence-based", round(rng.uniform(0.85, 0.99), 3), "1.0.0"))
        hla_lines = ["allele\tclass\tsource\tmethod\tconfidence\tversion"]
        hla_lines += ["\t".join(str(x) for x in row) for row in hla_rows]
        (patient_dir / f"{name}_hla.tsv").write_text("\n".join(hla_lines) + "\n")

        expr_genes = {v["gene"] for v in somatic} | {v["gene"] for v in germline} | set(HOUSEKEEPING)
        expr_lines = ["gene_id\tgene_symbol\ttranscript_id\texpression_value\tunit\tsource\tlevel"]
        for gene in sorted(expr_genes):
            transcript = _find_transcript(index, gene)
            gene_id = transcript["gene_id"] if transcript else ""
            base = HOUSEKEEPING.get(gene)
            if base is None:
                base = rng.uniform(5.0, 80.0)
            value = round(base * rng.uniform(0.6, 1.6), 2)
            tid = transcript["tid"] if transcript else ""
            expr_lines.append(f"{gene_id}\t{gene}\t{tid}\t{value}\tTPM\treal-reference\tGENE")
        (patient_dir / f"{name}_expression.tsv").write_text("\n".join(expr_lines) + "\n")

        doc = {"name": name, "dir": patient_dir, "somatic": somatic, "germline": germline}
        manifest_rows.append(
            f"{name},{len(somatic)},{len(germline)},{hla_rows and sum(1 for r in hla_rows if r[1]=='I')},"
            f"{sum(1 for r in hla_rows if r[1]=='II')},\"{'|'.join(sorted({v['gene'] for v in somatic}))}\""
        )
        for v in somatic:
            verification_rows.append(
                f"{name},{v['gene']},{v['protein_change']},{v['chrom']},{v['pos']},{v['ref']},{v['alt']}"
            )
        all_checked.extend(somatic)

    # final verification of every emitted somatic variant
    remaining = verify(index, all_checked)
    manifest_rows[0] = "patient,somatic_variants,germline_variants,class_i,class_ii,genes"
    (OUT_ROOT / "manifest.csv").write_text("\n".join(manifest_rows) + "\n")
    (OUT_ROOT / "verification.csv").write_text("\n".join(verification_rows) + "\n")

    print(f"wrote 50 patients to {OUT_ROOT}")
    print(f"verified somatic variants: {len(all_checked)}; mismatches: {len(remaining)}")
    if remaining:
        for v, reason in remaining[:10]:
            print("  MISMATCH:", v["gene"], v["protein_change"], reason)


if __name__ == "__main__":
    main()
