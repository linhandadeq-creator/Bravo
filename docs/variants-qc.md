# Variant Input & QC (Phase 2)

This phase turns raw VCF input into a QC'd variant dataset. It does **not**
perform variant annotation, HLA typing, neoantigen prediction or mRNA design.

## Inputs

- Tumor: `.vcf`, `.vcf.gz`
- Normal: `.vcf`, `.vcf.gz`
- Demo mode: synthetic tumor + synthetic normal VCF generated on demand.

Tumor and normal must be supplied as a pair. The relation is explicit: an
`AnalysisRun` references a tumor `Sample` and a normal `Sample`.

## Flow

```
Tumor VCF ─┐
           ├─► parse (pysam + structural scan) ─► QC ─► Variant dataset
Normal VCF ┘                                      └─► SomaticCandidate set
```

## Parsing

Parsing uses [`pysam`](https://pysam.readthedocs.io/). Before pysam runs, a raw
structural scan over the text (gunzipping `.vcf.gz` first) identifies records
that pysam cannot report individually:

- malformed records (wrong column count, non-numeric POS)
- missing required fields (CHROM / POS / REF / ALT)
- invalid alleles (REF = ALT, non-ACGTN, symbolic/structural, multiallelic)

Captured per record: CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO, FORMAT plus
DP, AD, AF and GT when present.

## Variant model

`chromosome`, `position`, `reference`, `alternate`, `quality`, `filter`,
`depth`, `allele_frequency`, `genotype`, `variant_type`, plus normalized
chromosome, validity flags and invalid reason.

## Reference build

Each `AnalysisRun` records an explicit `reference_build` (`GRCh37` / `GRCh38`).

- Tumor build ≠ Normal build → `FAILED` with an explicit error.
- Missing reference build → `BLOCKED`.

## Chromosome validation

`chr1` and `1` are treated as the same chromosome. Names are normalised to the
canonical `chr`-prefixed form and every conversion is recorded
(`chromosome_normalized`, `chromosome_normalized_flag`).

## Somatic candidates

Comparison is keyed on `(normalized chromosome, position, REF, ALT)` over unique
valid variants.

| Classification | Meaning |
| -------------- | ------- |
| `TUMOR_ONLY`   | Present only in tumor. A candidate — **not** confirmed somatic. |
| `NORMAL_ONLY`  | Present only in normal (likely germline). |
| `SHARED`       | Present in both with confident normal evidence. |
| `UNCERTAIN`    | Present in both, but normal depth/AF/GT is below the confidence threshold. |

## QC dashboard

Raw variants · Valid variants · Invalid variants · Duplicate variants ·
Tumor-only · Normal-only · Shared · Uncertain.

## Statuses (no silent fallback)

| Status | When |
| ------ | ---- |
| `PASS` | Pair parsed and all critical checks pass. |
| `FAILED` | Reference-build mismatch, or no unique valid variants. |
| `BLOCKED` | Missing normal VCF, missing reference build, or unparseable/format-invalid VCF. |

## Synthetic dataset

`app.services.synthetic.generate_synthetic_dataset` writes a deterministic pair
(`synthetic_tumor.vcf.gz`, `synthetic_normal.vcf`) containing shared variants
with differing allele frequencies, tumor-only variants, a normal-only variant,
a weak-evidence (uncertain) variant, a duplicate record, an invalid allele and a
malformed record. Expected counts live in `EXPECTED_SYNTHETIC`.
