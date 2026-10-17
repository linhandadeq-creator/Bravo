# Automated Scientific Validation (Phase 7)

The system must verify not only that it runs without errors, but that it produces
the **expected scientific results**. This layer executes a synthetic gold
dataset through the full pipeline and compares Expected vs Actual at every step.

## Framework

| Model | Purpose |
| ----- | ------- |
| `ValidationDataset` | The gold dataset definition and its expected results. |
| `ValidationReport` | One validation run: totals, pipeline health, categories, reproducibility. |
| `ValidationCase` | One Expected vs Actual comparison with a `PASS` / `FAIL` / `WARNING` status. |
| `AuditLog` | Scientific audit trail (step, timestamp, input, output, provider, version, parameters, status, error). |

## Synthetic gold dataset

`app.validation.gold` generates a fully synthetic dataset:

- **Tumor VCF**: chr1:1003 (MOCKGENE1 missense), chr1:1008 (synonymous),
  chr2:5003 (MOCKGENE2 missense), chr3:4000 (intergenic).
- **Normal VCF**: chr1:1003 and chr1:1008 → two `SHARED`, two `TUMOR_ONLY`.
- **HLA**: 4× Class I + 2× Class II.
- **Expression**: MOCKGENE1, MOCKGENE2 (transcript-level), TP53 (gene-level).
- **Expected** annotation, somatic candidates, neoantigen candidates, ranking
  behavior and construct are encoded in `EXPECTED`.

## Pipeline validation

```
VCF → QC → Tumor/Normal → Annotation → HLA → Expression
    → Candidate → Prediction → Ranking → Construct Simulation
```

Each stage produces `ValidationCase`s with `expected_result` and `actual_result`.

## Categories

- **INPUT_VALIDATION** — malformed VCF, missing field, invalid allele, reference
  build mismatch are all detected.
- **BIOLOGICAL_DATA_INTEGRATION** — tumor/normal matching, annotation mapping,
  HLA normalization, expression mapping.
- **PIPELINE_VALIDATION** — candidate generation, prediction provider, ranking.
- **PROVENANCE_VALIDATION** — input hash, software version, reference build,
  annotation version, prediction provider and parameters are all present.
- **REPRODUCIBILITY** — Run A vs Run B compared on candidate identities,
  prediction values, ranking scores, annotation and construct. Deterministic
  modules must match; if a module were randomised it must record its seed.
- **CONSTRUCT_VALIDATION** — representation, status, ordering, traceability and
  production sections.

## No silent failure

Every case is exactly one of `PASS`, `FAIL` (error) or `WARNING`. There is no
path that reports success while a check failed.

## Final validation

`POST /api/validation/run` executes the complete synthetic pipeline twice
(reproducibility) and returns a report. The build is labelled
**VALIDATED SOFTWARE BUILD** only when `failed == 0`.

> This certifies that the software computational pipeline passed its tests. It
> does **not** indicate clinical efficacy, patient response, or therapeutic
> effectiveness.

## UI

The Validation Dashboard shows Total Tests / Passed / Failed / Warnings,
Pipeline Health per stage, category summary, reproducibility, the cases table
(Expected vs Actual) and the scientific audit log.
