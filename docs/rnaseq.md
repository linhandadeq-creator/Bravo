# RNA-seq matrix quantification (v1)

Matrix-level tumor-vs-normal quantification for the expression stage. This is
**not** a read-alignment pipeline (STAR / salmon / kallisto are future work) —
it ingests a precomputed genes × samples matrix and derives honest, provenance-
complete quantitative calls.

## Input

`POST /api/analysis-runs/{id}/expression/quantify` (multipart: `file`, `fmt`,
`unit`, plus `tumor_samples` / `normal_samples` when needed).

The matrix is CSV/TSV with gene columns plus value columns. Two schemes:

1. **Paired columns** — auto-detected: `tumor_tpm`/`normal_tpm`,
   `tumor_value`/`normal_value`, `tumor_counts`/`normal_counts`,
   `tumor`/`normal`, `tumor_fpkm`/`normal_fpkm`.
2. **Sample columns** — declare the group columns explicitly:
   `tumor_samples=tumor_1,tumor_2&normal_samples=normal_1,normal_2`;
   the group value is the arithmetic mean of the group's samples.

## Quantification conventions (method `rnaseq-matrix-v1`, version 1.0.0)

- `tumor_value` / `normal_value`: group means in the input unit.
- `log2_fold_change = log2((tumor + 1) / (normal + 1))` — pseudocount **1**,
  recorded per row.
- `is_expressed`: tumor ≥ `expression_threshold` (default **1.0**).
- `differentially_expressed`: `is_expressed` **and** `|log2_fold_change| ≥ 1`.
- Missing normal sample: `log2_fold_change = log2(tumor + 1)` with an explicit
  note — data is never fabricated, and the gene is not called DE without a
  normal value.
- Missing tumor value: no log2FC, not expressed, explicit note.

## API

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/api/analysis-runs/{id}/expression/quantify` | Upload + quantify a matrix |
| GET | `/api/analysis-runs/{id}/expression/quantification` | Rows (filter `?differentially_expressed=true&gene_id=`) |
| GET | `/api/analysis-runs/{id}/expression/status` | Status now embeds a `quantification` summary |

Quantification rows are stored in `expression_quantifications` with method,
version, thresholds, sample layout and input hash. The tumor values are also
ingested as ordinary expression records so the downstream candidate pipeline
(tumor-expression evidence) keeps working.

## Scope note

No alignment, no transcript quantification from raw reads, no TMM/median
normalization across samples — the matrix is expected to be pre-normalized by
the user's pipeline. This v1 makes the tumor/normal differential signal
explicit, traceable and queryable; a full quantifier integration is a later
phase.
