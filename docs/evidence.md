# Variant evidence engine: gnomAD / ClinVar / COSMIC

Pluggable evidence providers annotate a run's QC'd tumor variants with
population frequency, known-driver and clinical-significance evidence. Every
record carries full provenance; failures are recorded as `FAILED` and never
masked by mock data.

| Provider | Status | Data |
| -------- | ------ | ---- |
| `mock`   | MOCK   | Deterministic demo/test evidence (clearly labelled). |
| `gnomad` | AVAILABLE | Real population frequency via the official gnomAD GraphQL API (no key). GRCh38 → `gnomad_r4` (fallback `r3`), GRCh37 → `gnomad_r2_1`. |
| `clinvar` | UNAVAILABLE until installed | Real clinical significance from a local tabix-indexed ClinVar VCF (NCBI weekly release). Fully offline at query time. |
| `cosmic` | UNAVAILABLE | Reserved adapter — requires a commercial COSMIC licence. |

## Install ClinVar data

```bash
./scripts/download_clinvar_vcf.sh          # GRCh38 → backend/storage/evidence/clinvar/
```

The provider auto-detects the file, or set `CLINVAR_EVIDENCE_VCF` explicitly.

## API

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET    | `/api/evidence/providers` | Provider status list |
| POST   | `/api/analysis-runs/{id}/evidence` | Annotate the run's QC'd tumor variants with selected (default: all usable) providers |
| GET    | `/api/analysis-runs/{id}/evidence` | Evidence records (filter `?variant_id=`) |
| GET    | `/api/analysis-runs/{id}/variants/{variant_id}` | Variant detail now includes `evidence` records |

```bash
curl -X POST localhost:8000/api/analysis-runs/<run>/evidence \
     -H 'Content-Type: application/json' -d '{"providers": ["mock", "gnomad", "clinvar"]}'
```

## Semantics

- **Population frequency** (`population_frequency`): global genome AC/AN
  (exome fallback) from gnomAD. High frequency suggests a germline/common
  variant — the platform *reports* it; interpretation is left to the
  researcher (no silent filtering).
- **Known driver** (`known_driver`): ClinVar pathogenic call on a
  cancer-associated condition. COSMIC slot reserved for licensed
  installations.
- **Clinical significance** (`clinical_significance`): ClinVar CLNSIG for
  the matched allele.
- **Provenance**: provider, provider version, source (dataset / VCF release
  date), identifiers (VCV accession, rsID), review status and lookup detail
  are stored per record.
- **Failure is explicit**: a gnomAD outage records `FAILED` records with the
  error; the mock provider is never substituted.

Evidence is surfaced in the variant detail view and the system manifest
(`variant_evidence_providers`). It is research evidence only — **not** a
clinical interpretation and not for clinical or human use.
