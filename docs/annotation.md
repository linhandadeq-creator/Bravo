# Variant Annotation Engine (Phase 3)

Turns the QC'd variant dataset into annotated variants with full provenance.

## Plugin interface

```python
class VariantAnnotator(ABC):
    name: str

    def metadata(self) -> ProviderMetadata: ...
    def annotate(self, variants: list[VariantInput], reference_context: ReferenceContext) -> list[AnnotationRecord]: ...
    def is_available(self) -> bool: ...
```

Providers register by name (`app/annotation/registry.py`).

| Provider | Status |
| -------- | ------ |
| `mock`   | Available. Deterministic transcript DB (`MockTranscripts`) + standard genetic code. |
| `vep`    | Available when the Ensembl REST service is reachable. Real gene/transcript/consequence/HGVSp via the official REST API; builds the real mutant peptide. |
| `offline`| Available once local reference data is installed. Real annotation with **no network at runtime** — see below. |
| `snpeff` | Reserved (requires the SnpEff runtime). |
| `annovar`| Reserved (requires an ANNOVAR licence/runtime). |

### Fully-offline provider

The `offline` provider computes real gene, transcript, coding consequence,
protein change and the mutant peptide from a local Ensembl release (GTF
transcript structure + CDS FASTA), independent of any web service. It is the
fallback for when `rest.ensembl.org` is down (HTTP 5xx).

Install the data once (Ensembl r112 GRCh38 by default):

```bash
./scripts/download_offline_reference.sh GRCh38
```

Data lives in `backend/storage/reference/<build>/` (override with
`OFFLINE_REFERENCE_DIR`). First use compiles a pickled interval index plus a CDS
SQLite store; subsequent annotation is fast and offline. Variants whose
reference base does not match (or that fall outside any transcript) are reported
`PARTIAL`/`unknown` rather than guessed. This provider never falls back to the
mock annotator.

## Annotation model

Gene, Gene ID, Transcript, Transcript ID, Consequence, Impact, Protein Change,
CDS Position, Protein Position.

### Consequences

`missense`, `frameshift`, `stop_gained`, `stop_lost`, `start_lost`,
`splice_related`, `inframe_insertion`, `inframe_deletion`, `synonymous`,
`unknown`.

### Impact

`HIGH`, `MODERATE`, `LOW`, `MODIFIER`.

## Statuses

| Status | Meaning |
| ------ | ------- |
| `ANNOTATED` | Annotation computed. |
| `PARTIAL`   | Consequence known but not fully modelled (e.g. protein change for indels). |
| `FAILED`    | Provider error, or reference-compatibility failure. Never rewritten to `UNKNOWN`. |
| `UNAVAILABLE` | Provider registered but not installed/configured. |

If any variant fails, the annotation run is `FAILED` and downstream is blocked.

## Reference compatibility

Each provider declares `reference_build`, `annotation_version` and
`transcript_source`. Before annotation the engine checks:

- VCF reference build is set,
- annotation reference build equals the VCF build,
- annotation version is declared,
- the transcript source is registered for that build.

Any mismatch is a hard `FAILED`.

## Provenance

Every `VariantAnnotation` stores: provider, provider_version, reference_build,
annotation_version, transcript_source, timestamp, parameters and input_hash
(per-variant and per-batch).

## Candidate filtering

Allowed consequences are configuration (`annotation_filter_configs`, editable via
`GET/PUT /api/projects/{id}/annotation-filter`). The default seed is
`missense,frameshift,stop_gained`. Filtering logic never hardcodes the rule and
never treats a `FAILED` annotation as `unknown`.

## Neoantigen gate

`GET /api/analysis-runs/{id}/neoantigen-input` returns only tumour variants that

- belong to a `PASS` analysis run,
- have a successful (non-`FAILED`/`UNAVAILABLE`) annotation run,
- carry an annotation for every variant,
- match the project's allowed consequences.

Otherwise it responds `409` with an explicit reason.

## Synthetic expected annotations

`tests/test_annotation.py` holds a table of input variant → expected consequence
→ expected protein change and compares it directly against the
`MockVariantAnnotator` output, so expected vs actual is verified automatically.
