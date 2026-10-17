# Neoantigen Candidate Engine (Phase 5)

## Data flow

```
SomaticCandidate + Annotation + HLA + Expression + Mutation Evidence
        │
        ▼
NeoantigenCandidate  ──►  PredictionResult  ──►  Research Candidate Score
```

Candidates are generated only for a `PASS` run with traceable annotations,
available HLA and available expression.

## NeoantigenCandidate

`candidate_id`, `variant_id`, `gene`, `gene_id`, `transcript`, `transcript_id`,
`protein_change`, `consequence`, `impact`, `peptide_representation`,
`peptide_sequence`, `hla_allele`, `hla_class`, `expression_evidence`,
`mutation_evidence`, `prediction_status`, `status`, `ranking_score`,
`ranking_evidence`, `ranking_configuration_id`.

`peptide_representation` is the research-object identifier
(`GENE|protein_change|peptide`). One candidate is produced per (tumour variant,
valid HLA allele).

### Statuses

`GENERATED`, `PREDICTED`, `RANKED`, `REJECTED`, `UNCERTAIN`, `FAILED`.
Candidates whose consequence is outside the project's allowed set are stored as
`REJECTED` (never predicted or ranked).

## Prediction provider architecture

```python
class PredictionProvider(ABC):
    provider_name: str
    provider_version: str
    is_mock: bool
    def supported_hla(self) -> list[str]: ...
    def health_check(self) -> ProviderStatus: ...
    def validate_input(self, inputs) -> ValidationResult: ...
    def predict(self, inputs) -> list[PredictionOutput]: ...
```

Statuses: `MOCK`, `AVAILABLE`, `UNAVAILABLE`, `FAILED`.

| Provider | Status | Notes |
| -------- | ------ | ----- |
| `mock` | MOCK | Deterministic pseudo binding score. Explicitly marked mock. |
| `external` | UNAVAILABLE | Reserved adapter slot for a validated real tool. |

`ExternalPredictionAdapter` is the standard interface for real tools. No tool is
hardcoded; a tool is integrated by subclassing and registering it.

If the selected provider is not `MOCK`/`AVAILABLE`, every candidate gets
`prediction_status=UNAVAILABLE`, no `PredictionResult` rows are written, and no
ranking score is produced. **The mock provider is never silently substituted.**

## PredictionResult

`candidate_id`, `hla`, `prediction_value`, `metric_name`, `provider`,
`provider_version`, `status`, `input_hash`, `timestamp`.

## Candidate ranking

`CandidateRankingEngine` combines normalized evidence:

| Component | Source | Normalization |
| --------- | ------ | ------------- |
| presentation | prediction value | clamp 0–1 |
| expression | expression value | value / cap (default 50) |
| mutation | tumour allele frequency | clamp 0–1 |
| tumor_specificity | somatic classification | TUMOR_ONLY 1.0, UNCERTAIN 0.5, else 0 |
| variant_quality | QUAL | value / cap (default 100) |

`Research Candidate Score = Σ normalized_weight × component × 100`.

> Research Candidate Score is a candidate ranking metric only. It is **not** a
> clinical efficacy probability, a patient response probability, or a vaccine
> effectiveness probability.

## Ranking configuration

Weights are stored per project (`ranking_configurations`) with an id and
version, editable via `GET/PUT /api/projects/{id}/ranking-config`. Every
`AnalysisRun` records the configuration used (`ranking_configuration_id` and a
`ranking_config` snapshot).

## UI

The Neoantigen table shows Candidate, Gene, Mutation, HLA, Expression,
Prediction, Specificity, Quality, Research Score and Status, with sorting,
filtering, search and a detail view. The provider selector always shows whether
the **Mock Provider** or a **Real Prediction Provider** is active; an
unavailable provider renders `PREDICTION UNAVAILABLE`. The candidate detail page
shows full provenance: Variant, Annotation, HLA, Expression, Prediction,
Ranking, Provider and versions.

## Tests

`tests/test_neoantigen.py` covers the full chain (synthetic variant → candidate →
prediction → ranking) with expected genes (`MOCKGENE1`, `MOCKGENE2`), protein
changes (`p.K2E`, `p.P2S`) and statuses, plus the unavailable-provider path
asserting `PREDICTION UNAVAILABLE` with no mock substitution.
