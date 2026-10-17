# Report Generation (Phase 8)

Generates a research report for an analysis run by aggregating every stage of
the pipeline.

## Contents

- Overview: project, run, status, mode, reference build, software version.
- QC: raw / valid / invalid / duplicate counts.
- Tumor/normal classification counts.
- Variant annotation table (locus, gene, transcript, consequence, protein).
- HLA typing table (allele, class, method, confidence, validity).
- Expression table (gene, transcript, level, value, unit).
- Neoantigen candidates ranked by research score (prediction status/value, score).
- Construct simulation (representation, status, sequence length).
- Latest validation report summary.
- Research-use disclaimer.

## Formats

| Format | Output |
| ------ | ------ |
| `json` | Full structured report |
| `markdown` | Human-readable report |
| `html` | Self-contained HTML |
| `csv` | Candidate table |
| `pdf` | Directly generated PDF (server-side, Chinese-capable, no browser print) |

PDF is produced with ReportLab using the built-in `STSong-Light` CJK font, so
no browser or system font is required. Stored PDF reports are kept base64-encoded
and returned as `application/pdf` on download; the direct endpoint streams the
PDF bytes.

## API

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/api/analysis-runs/{id}/reports` | Generate and store a report |
| GET | `/api/reports` | List reports (`project_id`, `analysis_run_id`) |
| GET | `/api/reports/{id}` | Report detail incl. content |
| GET | `/api/reports/{id}/download` | Download a stored report |
| GET | `/api/analysis-runs/{id}/report?format=pdf\|json\|markdown\|html\|csv` | Direct export |

## Model

`Report`: `analysis_run_id`, `project_id`, `title`, `format`, `status`,
`summary` (JSON counts), `content`, `software_version`, `generated_by`,
`created_at`.

## Disclaimer

Every report embeds: *“仅用于研究用途……不代表临床有效性、患者响应或治疗有效性，不可用于临床决策或人体使用。”*

## Tests

`tests/test_reports.py` covers generation, listing, detail, download and all
direct export formats.
