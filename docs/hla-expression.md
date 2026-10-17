# HLA & Expression Integration (Phase 4)

Provides the HLA typing and RNA expression context required before variants may
enter the Neoantigen Engine.

## HLA

### Model — `HLAProfile`

`allele`, `allele_class` (I/II), `locus`, `source`, `method`, `confidence`,
`version`, plus validation (`is_valid`, `is_duplicate`, `invalid_reason`) and
provenance (`normalization_method`, `input_hash`, `timestamp`).

### Input

- JSON (e.g. `{"alleles": [{"allele": "HLA-A*02:01", "class": "I"}]}`)
- CSV / TSV (`allele,class,source,method,confidence,version`)
- Manual research input (JSON array via `POST /hla`)

### Normalization & validation

Canonical form: `HLA-<LOCUS>*<field>:<field>` (e.g. `A0201` → `HLA-A*02:01`).
The class is derived from the locus. Detected problems:

| Check | Result |
| ----- | ------ |
| allele format | `invalid_reason` + `is_valid=false` |
| unknown locus | invalid |
| class mismatch | invalid |
| duplicate allele | `is_duplicate=true` (de-duplicated) |

Status: `HLA_AVAILABLE`, `HLA_INVALID` (any invalid allele), `HLA_UNAVAILABLE`
(no data). Invalid HLA never enters the prediction pipeline.

## Expression

### Model — `ExpressionRecord`

`level` (`GENE` / `TRANSCRIPT`), `gene_id`, `gene_symbol`, `transcript_id`,
`expression_value`, `unit`, `source`, plus normalization audit
(`raw_gene_id`, `raw_transcript_id`, `gene_id_changed`, `transcript_id_changed`,
`gene_id_resolved`) and provenance (`normalization_method`, `input_hash`,
`version`, `timestamp`).

### Input

CSV / TSV: `gene_id,gene_symbol,transcript_id,expression_value,unit,source,level`.

### Identifier normalization

- Ensembl gene IDs: version suffix stripped (`ENSG00000141510.12` → `ENSG00000141510`).
- Gene symbols mapped to Ensembl IDs (`TP53` → `ENSG00000141510`).
- Ensembl transcript IDs: version stripped (`ENST00000269305.9` → `ENST00000269305`).
- Unresolved identifiers are preserved and marked unresolved — never fabricated.

Every conversion is recorded on the record.

Status: `EXPRESSION_AVAILABLE`, `EXPRESSION_INVALID` (no valid rows),
`EXPRESSION_UNAVAILABLE` (no data). Expression is never fabricated.

## Synthetic dataset

`POST /api/projects/{id}/synthetic-integration` builds a full chain: synthetic
tumor/normal VCFs → analysis → mock annotation → synthetic HLA (Class I + II) →
synthetic expression. Expression covers `MOCKGENE1` / `MOCKGENE2`, the mock
transcripts used by the annotator, so `linked_genes` is non-empty.

## Readiness gate

`GET /api/analysis-runs/{id}/neoantigen-readiness` returns `200` only when:

- the analysis run is `PASS`,
- annotations are traceable (Phase 3 gate),
- HLA status is `HLA_AVAILABLE`,
- expression status is `EXPRESSION_AVAILABLE`.

Otherwise it returns `409` with the explicit blocking reasons. The report also
lists `annotated_genes`, `expressed_genes`, `linked_genes` and
`genes_without_expression`.
