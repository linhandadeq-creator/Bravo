# mRNA Construct Research Simulation (Phase 6)

> **Research simulation only.** All generated content (dosing regimen, clinical
> protocol, manufacturing SOP, parameters, release criteria, formulation,
> production instructions) is simulated from mock/synthetic data. It is **not**
> a validated therapeutic or manufacturing design and is **not for clinical or
> human use**.

## SimulationConstruct

`construct_id`, `analysis_run_id`, ordered `candidate_ids`, `ordering`,
`simulation_format`, `status`, `created_at`, plus `construct_representation`,
`sequence`, `selected_by`, `selected_at`, `candidate_version`, `qc_summary`,
`validation` and `simulation_output`.

## Candidate selection

Available and selected candidates are shown in the Construct Builder. Users can
**Select**, **Remove** and **Reorder**. Each `ConstructItem` records
`selected_by`, `selected_at` and `candidate_version` granularly.

## Construct representation

```
[5PRIME] [ANTIGEN_001] [SPACER] [ANTIGEN_002] [SPACER] [ANTIGEN_003] [3PRIME]
```

A simulated mRNA sequence is assembled from the selected mock peptide segments
(5' UTR, Kozak, per-antigen coding segment, G4S linker spacers, stop, 3' UTR,
poly(A)).

## Simulation QC

| Check | Description |
| ----- | ----------- |
| candidate_exists | Every id resolves to a candidate |
| duplicate_candidates | No repeated candidate |
| same_analysis_run | Candidates belong to this run |
| provenance | Candidate → Variant → Annotation → HLA → Prediction → Ranking complete |
| hla_information | HLA present |
| prediction_status | `MOCK`/`AVAILABLE` (not `UNAVAILABLE`) |
| ranking_status | Candidate is `RANKED` with a score |
| construct_ordering | Contiguous 1..N with `ANTIGEN_001..N` labels |
| missing_data | Peptide data present |
| candidate_selection | At least one candidate |

### Status

`DRAFT` (empty selection) · `VALIDATED_SIMULATION` (all checks pass) ·
`INVALID` (any check fails) · `LOCKED` (validated then locked; no further edits).

## Traceability

The QC report includes the full chain per candidate:

```
Candidate → Variant → Annotation → HLA → Prediction → Ranking
```

## Production operation file

`GET /api/constructs/{id}/export?format=json|csv|report` returns:

- **json** — construct, QC and the full simulated production package.
- **csv** — the ordered build sheet (position, label, candidate, gene, mutation,
  HLA, spacer, candidate version).
- **report** — a markdown research report with representation, ordering,
  validation, traceability and the simulated production sections.

## Tests

`tests/test_construct.py` covers candidate selection, duplicate detection,
missing candidate, cross-run candidate, unranked candidate, ordering, full
traceability, empty→invalid validation, locking and all export formats.
