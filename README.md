# Bravo — Personalized Neoantigen Analysis Platform

A scientific computing and simulation platform for personalized neoantigen analysis.
**Research simulation only — not for clinical or human use.** Every output is labelled
with its provenance; unavailable tools are never silently substituted by mock results.

## Pipeline (implemented)

```
VCF → QC & somatic classification → annotation (Ensembl VEP REST / fully offline)
    → HLA & expression ingest → candidate generation (UniProt self-filter)
    → prediction (MHCflurry · MHCnuggets · MixMHCpred · PRIME · consensus)
    → ranking (agretopicity + evidence) → mRNA construct design (codon engine +
      MPRA-trained 5'UTR model + sequence QC) → polyepitope assembly with
      junction audit → production blueprint package → reports (PDF/MD/HTML/CSV)
```

All stages are real, reproducible and covered by tests (345 tests, 87% coverage).
Upstream steps not yet included: variant calling from reads, HLA typing and
read-level RNA quantification (see `docs/roadmap.md`).

## Stack

| Layer      | Technology                                    |
| ---------- | --------------------------------------------- |
| Frontend   | Next.js, React, TypeScript, TailwindCSS, shadcn/ui |
| Backend    | Python, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Database   | PostgreSQL                                    |
| Cache      | Redis                                         |
| Deployment | Docker, Docker Compose                        |

## Project structure

```
neoantigen-platform/
├── frontend/          # Next.js app (Dashboard, Projects, Variants, ...)
├── backend/           # FastAPI app, models, schemas, Alembic migrations
├── database/          # PostgreSQL bootstrap assets
├── example_data/      # Sample inputs for future phases
├── scripts/           # Developer helper scripts
├── docs/              # Documentation
├── docker/            # Docker helper assets
├── docker-compose.yml
├── README.md
└── .env.example
```

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

| Service   | URL                         |
| --------- | --------------------------- |
| Frontend  | http://localhost:3000       |
| Backend   | http://localhost:8000       |
| Swagger   | http://localhost:8000/docs  |
| ReDoc     | http://localhost:8000/redoc |

On startup the backend waits for PostgreSQL, runs Alembic migrations, seeds a
demo project (`Demo Cancer Project`), and serves the API.

## Local development (without Docker)

See [`docs/development.md`](docs/development.md) for running the backend and
frontend directly.

## API (Phase 1)

| Method | Path                                      | Description                     |
| ------ | ----------------------------------------- | ------------------------------- |
| GET    | `/api/health`                             | Health check                    |
| GET    | `/api/projects`                           | List projects                   |
| POST   | `/api/projects`                           | Create a project                |
| GET    | `/api/projects/{id}`                      | Retrieve a project              |
| PATCH  | `/api/projects/{id}`                      | Update a project                |
| GET    | `/api/projects/{id}/samples`              | List a project's samples        |
| POST   | `/api/analysis-runs/synthetic`            | Generate synthetic pair + QC    |
| POST   | `/api/analysis-runs/upload`               | Upload tumor/normal VCFs + QC   |
| POST   | `/api/analysis-runs`                      | Run on existing samples         |
| GET    | `/api/analysis-runs`                      | List analysis runs              |
| GET    | `/api/analysis-runs/{id}`                 | Run detail incl. QC summary     |
| GET    | `/api/analysis-runs/{id}/variants`        | QC'd variants                   |
| GET    | `/api/analysis-runs/{id}/somatic-candidates` | Tumor/normal classifications |
| GET    | `/api/annotation/providers`               | List annotation providers       |
| POST   | `/api/analysis-runs/{id}/annotate`        | Run a variant annotator         |
| GET    | `/api/analysis-runs/{id}/annotations`     | Annotation records + provenance |
| GET    | `/api/analysis-runs/{id}/annotated-variants` | Filtered annotated variants  |
| GET    | `/api/analysis-runs/{id}/variants/{variant_id}` | Variant detail + evidence |
| GET    | `/api/analysis-runs/{id}/neoantigen-input` | Downstream traceability gate |
| GET/PUT | `/api/projects/{id}/annotation-filter`   | Allowed consequences config     |
| GET    | `/api/analysis-runs/{id}/hla`             | HLA profiles                    |
| GET    | `/api/analysis-runs/{id}/hla/status`      | HLA validation status           |
| POST   | `/api/analysis-runs/{id}/hla`             | Manual HLA input                |
| POST   | `/api/analysis-runs/{id}/hla/upload`      | Upload HLA (JSON/CSV/TSV)       |
| GET    | `/api/analysis-runs/{id}/expression`      | Expression records              |
| GET    | `/api/analysis-runs/{id}/expression/status` | Expression status             |
| POST   | `/api/analysis-runs/{id}/expression`      | Manual expression input         |
| POST   | `/api/analysis-runs/{id}/expression/upload` | Upload expression (CSV/TSV)   |
| POST   | `/api/analysis-runs/{id}/expression/quantify` | RNA-seq matrix quantification (tumor/normal log2FC) |
| GET    | `/api/analysis-runs/{id}/expression/quantification` | Quantification rows |
| GET    | `/api/analysis-runs/{id}/integration-status` | Variant+Annotation+HLA+Expression |
| GET    | `/api/analysis-runs/{id}/neoantigen-readiness` | Readiness gate (409 if blocked) |
| POST   | `/api/projects/{id}/synthetic-integration` | One-click synthetic dataset   |
| GET    | `/api/prediction/providers`               | Prediction providers + status   |
| GET/PUT | `/api/projects/{id}/ranking-config`      | Ranking weights configuration   |
| POST   | `/api/analysis-runs/{id}/neoantigen/run`  | Generate + predict + rank       |
| POST   | `/api/analysis-runs/{id}/neoantigen/generate` | Generate candidates only    |
| GET    | `/api/analysis-runs/{id}/neoantigen-candidates` | List/filter/sort/search   |
| GET    | `/api/neoantigen-candidates/{id}`         | Candidate detail + provenance   |
| POST   | `/api/analysis-runs/{id}/constructs`      | Create simulation construct     |
| GET    | `/api/analysis-runs/{id}/constructs`      | List constructs                 |
| GET    | `/api/constructs/{id}`                    | Construct detail                |
| PUT    | `/api/constructs/{id}/selection`          | Select / reorder candidates     |
| POST   | `/api/constructs/{id}/validate`           | Run construct QC                |
| POST   | `/api/constructs/{id}/lock`               | Lock a validated construct      |
| GET    | `/api/constructs/{id}/export`             | Production operation file (json/csv/report) |
| POST   | `/api/validation/run`                     | Run full pipeline validation    |
| GET    | `/api/validation/reports`                 | List validation reports         |
| GET    | `/api/validation/reports/{id}`            | Report + cases + audit log      |
| GET    | `/api/validation/datasets`                | List validation datasets        |
| POST   | `/api/analysis-runs/{id}/reports`         | Generate & store a report       |
| GET    | `/api/reports`                            | List reports                    |
| GET    | `/api/reports/{id}`                       | Report detail + content         |
| GET    | `/api/reports/{id}/download`              | Download a stored report        |
| GET    | `/api/analysis-runs/{id}/report`          | Direct export (pdf/json/markdown/html/csv) |
| POST   | `/api/one-click/generate`                 | One-click user module (upload → mRNA) |
| GET    | `/api/constructs/{id}/blueprint`          | mRNA blueprint (pdf/svg/html/json) |
| GET    | `/api/constructs/{id}/production-package` | Production blueprint package (json/markdown) |
| GET    | `/api/constructs/{id}/worklist`           | Experimental worklist (CSV)     |

## Variant input & QC (Phase 2)

Paired tumor/normal VCFs (`.vcf` or `.vcf.gz`) are parsed with
[`pysam`](https://pysam.readthedocs.io/) and pass through a raw structural scan
that flags malformed records, missing required fields, invalid alleles and
duplicates. Chromosome naming (`chr1` vs `1`) is normalised and the conversion
is recorded. Every run records an explicit reference build; a mismatch between
the tumor and normal samples is a hard `FAILED`. Missing normal VCF, missing
reference build or an unparseable file is `BLOCKED`. Nothing falls back to a
default silently.

Tumor/normal comparison produces `SomaticCandidate` classifications
(`TUMOR_ONLY`, `NORMAL_ONLY`, `SHARED`, `UNCERTAIN`). A `TUMOR_ONLY` candidate is
**not** asserted to be a true somatic mutation — it is a candidate that requires
orthogonal evidence. See [`docs/variants-qc.md`](docs/variants-qc.md).

## Variant Evidence Engine (population / clinical)

Pluggable evidence providers annotate QC'd variants with **population
frequency (gnomAD, real API)**, **clinical significance and known-driver
evidence (ClinVar, local VCF)** and a reserved **COSMIC** slot (licence
required), plus a deterministic `mock` provider. All records carry full
provenance and a failed lookup is recorded as `FAILED` — never silently
replaced. See [`docs/evidence.md`](docs/evidence.md).

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET    | `/api/evidence/providers` | Evidence provider status |
| POST   | `/api/analysis-runs/{id}/evidence` | Annotate run variants |
| GET    | `/api/analysis-runs/{id}/evidence` | Evidence records |

## Variant Annotation Engine (Phase 3)
Annotation is pluggable via the `VariantAnnotator` interface
(`annotate(variants, reference_context)`). A deterministic `MockVariantAnnotator`
ships for demos and tests; `VEP`, `SnpEff` and `ANNOVAR` are registered as
reserved (unavailable) providers. Each annotation carries the gene, transcript,
gene/transcript IDs, consequence, impact, protein change, CDS position and
protein position.

Providers declare their `reference_build`, `annotation_version` and
`transcript_source`; the engine verifies these against the run's VCF reference
build before accepting any result. Statuses are `ANNOTATED`, `PARTIAL`, `FAILED`
and `UNAVAILABLE` — a `FAILED` result is never downgraded to `UNKNOWN`.

Every result stores provenance (provider, provider version, reference build,
annotation version, timestamp, parameters, input hash). Consequence filtering is
configurable per project and never hardcoded. The `neoantigen-input` gate
refuses any variant without a traceable annotation. See
[`docs/annotation.md`](docs/annotation.md).

### Real providers

| Provider | Status | Notes |
| -------- | ------ | ----- |
| `mock` | ANNOTATED | Deterministic mock transcripts (demos/tests). |
| `vep` | ANNOTATED | **Ensembl VEP via the official REST API** — real gene, transcript, consequence, impact, HGVSp positions. Fetches the reference CDS from Ensembl and builds the **real mutant peptide** (`mutated_peptide`) used downstream. |
| `offline` | ANNOTATED | **Fully-offline annotation** from a local Ensembl GTF + CDS FASTA — real gene, transcript, consequence, protein change and mutant peptide with **no network at runtime** (works during Ensembl outages). |
| `snpeff` / `annovar` | UNAVAILABLE | Reserved. |

VEP uses the Ensembl REST API (GRCh38 `rest.ensembl.org`, GRCh37
`grch37.rest.ensembl.org`); the release is recorded as the annotation version.
If VEP is unreachable, annotation is reported `UNAVAILABLE`/`FAILED` — never
silently replaced by the mock annotator. Reference CDS sequences are cached
under `storage/ensembl_cache/`. Requests retry with backoff.

Because the public Ensembl REST service is occasionally unavailable (HTTP 5xx at
the provider), the `offline` provider is the outage-proof option. Install its
data once:

```bash
./scripts/download_offline_reference.sh GRCh38   # Ensembl r112 GTF + CDS → builds index
```

Data lives in `backend/storage/reference/<build>/` (override with
`OFFLINE_REFERENCE_DIR`). The provider compiles a pickled interval index plus a
CDS SQLite store on first use; the reference is never fetched from the network
at annotation time.

### Research-grade building blocks

- **Peptide enumeration** — the mutant context (up to 11 aa) is expanded into all
  8–11mer epitope windows containing the mutation; MHCflurry predicts each and
  the best presentation is kept (`detail.n_windows`).
- **Codon-optimised construct** — the simulated mRNA sequence uses human-preferred
  codons.
- **Self-protein off-target filter** — set `HUMAN_PROTEOME_FASTA` to a human
  reference proteome; peptides that exactly match a self 9-mer are flagged and
  excluded (status `REJECTED`, `mutation_evidence.self_similar`). When not
  configured the filter is explicitly unavailable.
- **External evidence data** — a **UniProt human reference proteome** powers the
  self-protein off-target filter; public **MS / measured-ligand** data bundled
  with MHCflurry powers a presentation-evidence lookup (flags candidates with
  direct immunopeptidome evidence). Both are reported in
  `GET /api/system/manifest`.
- **Reproducibility manifest** — `GET /api/system/manifest` lists tool/package
  versions, reference builds, provider availability, self-filter and MS-evidence
  status; every report embeds a **Methods & versions** section.

## HLA & Expression integration (Phase 4)

`HLAProfile` covers Class I and Class II alleles with source, method,
confidence and version. A normalization layer canonicalizes alleles
(`A0201` → `HLA-A*02:01`), derives the class from the locus and flags format
errors, unknown loci, class mismatches and duplicates. Invalid alleles are
recorded but blocked from the prediction pipeline.

`ExpressionRecord` covers gene- and transcript-level values with a gene/transcript
identifier normalization layer that records every conversion (version stripping,
symbol → Ensembl). Missing data is explicit: `HLA_UNAVAILABLE` and
`EXPRESSION_UNAVAILABLE`, never fabricated, and dependent steps are blocked.

All records store provenance (source, input hash, normalization method,
version, timestamp). A one-click synthetic integration ties synthetic HLA and
expression to the Phase 3 synthetic variants. The `neoantigen-readiness` gate
requires Variant + Annotation + HLA + Expression together. See
[`docs/hla-expression.md`](docs/hla-expression.md).

## Neoantigen Candidate Engine (Phase 5)

`SomaticCandidate + Annotation + HLA + Expression + Mutation Evidence` →
`NeoantigenCandidate` → prediction → ranking. Candidates store the gene,
transcript, protein change, peptide representation, HLA allele, expression and
mutation evidence, prediction status, ranking score and the ranking
configuration used.

Prediction is pluggable via the `PredictionProvider` interface (`provider_name`,
`provider_version`, `supported_hla`, `predict`, `validate_input`,
`health_check`) with statuses `MOCK` / `AVAILABLE` / `UNAVAILABLE` / `FAILED`.
Real providers are integrated without hardcoding any single tool:

| Provider | Status | Notes |
| -------- | ------ | ----- |
| `mock` | MOCK | Deterministic pseudo score for demos/tests. |
| `mhcflurry` | AVAILABLE | **MHCflurry 2.3 — Class I presentation** (binding + processing + presentation). |
| `mhcnuggets` | AVAILABLE | **MHCnuggets 2.4 — Class II binding** (BA models), run in an isolated Keras-2 venv via subprocess. |
| `panel` | AVAILABLE | **Combined Class I (MHCflurry) + Class II (MHCnuggets)** for CD8+CD4 coverage in one run. |
| `external` | UNAVAILABLE | Reserved real-tool adapter slot. |

Class II model download / setup:

```bash
# isolated Keras-2 runtime for MHCnuggets (does not affect the main venv)
uv venv --python 3.11 backend/.venv-mhcii
uv pip install --python backend/.venv-mhcii/bin/python "tensorflow==2.15.0" "numpy<2" mhcnuggets
```

NetMHCpan / NetMHCIIpan (licence required, DTU Health Tech) are fully
integrated adapters: batched per-allele invocation, Class I (8–14 aa) and
Class II (9–30 aa) semantics, best-`%Rank` row selection and binary version
detection. See [`docs/prediction-tools.md`](docs/prediction-tools.md) and
`scripts/setup_netmhcpan.sh`.

`MHCFlurryProvider` predicts Class I alleles with
`Class1PresentationPredictor` and stores `binding_affinity`,
`processing_score`, `presentation_score` (and percentiles), the model name and
version plus per-result provenance. Install and download the model with:

```bash
pip install -r backend/requirements.txt      # mhcflurry>=2.3,<2.4
./scripts/download_mhcflurry_models.sh        # models_class1_presentation
```

The UI always states whether the **Mock Provider** or a **Real Prediction
Provider** is active; Class II / unsupported inputs become `PREDICTION
UNAVAILABLE` and MHCflurry failures are surfaced as errors — the mock provider is
never substituted.

`CandidateRankingEngine` computes a **Research Candidate Score** from
presentation, expression, mutation, tumour-specificity and variant-quality
evidence. This is a ranking metric only — not a clinical efficacy, patient
response, or vaccine effectiveness probability. Weights are user-configurable
per project and every run records the configuration used. See
[`docs/neoantigen.md`](docs/neoantigen.md).

## mRNA Construct Research Simulation (Phase 6)

A computational research-simulation module. `SimulationConstruct` records the
construct id, analysis run, ordered candidate ids, ordering, simulation format,
status and creation time. Candidates can be selected, removed and reordered,
recording `selected_by`, `selected_at` and `candidate_version`.

Three simulation formats are supported: **`mRNA-LNP`** (linear), **`circRNA`**
(circular RNA via PIE self-splicing + IRES, no cap/poly(A)) and **`saRNA`**
(self-amplifying replicon with a simulated replicase cassette + subgenomic
promoter). See [`docs/simulation-formats.md`](docs/simulation-formats.md).

The construct uses an abstract representation
(`[5PRIME] [ANTIGEN_001] [SPACER] [ANTIGEN_002] ... [3PRIME]`) and derives a
simulated nucleic-acid design and a simulated production package (human dosing,
clinical treatment protocol, laboratory manufacturing SOP, manufacturing
parameters, release criteria, formulation, production instructions). Simulation
QC validates existence, duplicates, run membership, full provenance, HLA,
prediction and ranking status, ordering and missing data; the status is `DRAFT`,
`VALIDATED_SIMULATION`, `INVALID` or `LOCKED`. Outputs are available as JSON,
CSV or a research report — a simulated production operation file.

> All generated content is a research simulation from mock data and is **not for
> clinical or human use**. See [`docs/simulation.md`](docs/simulation.md).

## Production Blueprint Engine

The construct sequence is produced by a **constraint-based design engine**
(`app/blueprint/`) rather than naive concatenation:

- **Constraints**: GC window (target 40–60%, hard 30–70%), no homopolymer ≥ 6,
  no direct repeat ≥ 12 bp, no common/Type-IIS restriction sites, no hidden
  polyadenylation signals (AATAAA/ATTAAA), CAI ≥ 0.65. Optimised with a seeded
  hill-climb (deterministic).
- **Sequence QC / release gate**: computes manufacturability metrics and returns
  `PRODUCTION_READY` / `DESIGN_FAILED` (with a 0–100 score). Only designs passing
  all hard checks are marked production-ready.
- **Production package** (`/production-package`): sequence design + region map,
  sequence QC, IVT template (T7 + sequence), primers, cloning note, LNP
  formulation template and derived release criteria — all from the sequence.
- **Experimental worklist** (`/worklist`, CSV): candidates with peptide/HLA/
  prediction/expression/self-filter columns plus suggested controls.

> This is an in-silico research design engine. It maximises *in-silico*
> manufacturability and epitope quality; actual lab qualification rate must be
> established with wet-lab data. Outputs are unvalidated and not for clinical or
> human use. See [`docs/production-blueprint-plan.md`](docs/production-blueprint-plan.md).

## Automated Scientific Validation (Phase 7)

The platform is not only checked for "did it crash" but for **"did it produce
the expected scientific result"**. A fully synthetic gold dataset runs through
the entire pipeline (VCF → QC → Tumor/Normal → Annotation → HLA → Expression →
Candidate → Prediction → Ranking → Construct Simulation). Every step records
Expected vs Actual with `PASS` / `FAIL` / `WARNING`.

Categories: input validation (malformed VCF, missing field, invalid allele,
reference mismatch), biological data integration (tumor/normal matching,
annotation mapping, HLA normalization, expression mapping), pipeline validation
(candidate generation, prediction provider, ranking), provenance validation
(input hash, versions, reference build, provider, parameters) and
reproducibility (Run A vs Run B).

Failures are never silent: every case is `PASS`, `FAIL` (error) or `WARNING`,
and a scientific audit log records step, timestamp, input, output, provider,
version, parameters, status and error. `Run Full Validation` returns
**VALIDATED SOFTWARE BUILD** only when all critical tests pass.

> This certifies the software computational pipeline passed its tests. It does
> **not** indicate clinical efficacy, patient response, or therapeutic
> effectiveness. See [`docs/validation.md`](docs/validation.md).

## Report Generation (Phase 8)

A report aggregates every stage of an analysis run — QC, somatic classification,
annotation, HLA, expression, neoantigen candidates, prediction, ranking,
construct simulation and the latest validation report — into a single research
report. Formats: **JSON**, **Markdown**, **HTML**, **CSV** (candidate table) and
**PDF** (generated server-side, no browser printing needed, Chinese-capable).
Reports are persisted with a summary and a software-version stamp, listed per
project/run, and downloadable. Every report embeds the research-use disclaimer.
See [`docs/reports.md`](docs/reports.md).

## One-Click User Module (Phase 9)

A single upload-driven module: the user supplies a tumor VCF (and a paired
normal VCF, optionally HLA and expression files) and the platform runs the whole
validated pipeline automatically — QC → annotation → HLA → expression →
candidates → prediction → ranking → construct → **mRNA blueprint** → report.

- `POST /api/one-click/generate` (multipart). `demo=true` runs the synthetic
  dataset end-to-end.
- Missing normal VCF / HLA / expression is reported as **BLOCKED** with an
  explicit message; data is never fabricated. `use_synthetic_context=true`
  explicitly substitutes synthetic HLA/expression for demos (clearly labelled).
- Produces an mRNA blueprint: ordered segments, simulated sequence and an SVG
  schematic (`GET /api/constructs/{id}/blueprint?format=json|svg|html`), plus a
  full HTML report.

> The blueprint is a research schematic built from simulated data and is **not
> for clinical or human use**. See [`docs/user-module.md`](docs/user-module.md).

## 桌面应用（macOS）

Bravo 可作为原生桌面软件运行：双击 `Bravo.app` 打开一个**原生窗口**（无浏览器
地址栏），应用会在后台自动完成数据库迁移与初始化，启动本地后端（FastAPI +
SQLite）与已构建的前端，窗口内即为完整平台。

```bash
./scripts/build_desktop_app.sh     # 构建前端 + 生成 ~/Desktop/Bravo.app 与 Bravo.command
```

- `Bravo.app`：原生窗口入口（双击启动），运行时数据写入
  `~/Library/Application Support/Bravo/`（数据库、存储），日志见 `.run/desktop.log`。
- 桌面运行时依赖 `desktop/.venv`（pywebview，构建脚本自动创建）。
- 关闭窗口即自动停止后端/前端进程。

也可以使用轻量启动入口（浏览器方式）：

```bash
./scripts/install_desktop.sh
```

会在桌面生成启动入口与 `Bravo.command`；启动后打开浏览器。

```bash
./scripts/start_platform.sh   # 启动（幂等，已运行则直接打开）
./scripts/stop_platform.sh    # 停止前后端
```

日志与进程号写入 `.run/`（已 gitignore）。

## Project module (patient registration)

Projects register a **patient** and attach **registration files** (tumor VCF,
normal VCF, HLA, expression) which are then auto-filled across the module
pages (Variants / HLA / Expression / One-Click). Each project has **notes**
and **reminders** with due dates, and the HLA / Expression pages expose an
explicit **Analyze** action that re-validates uploaded data and shows a
detailed result. Light, optional interface **sound effects** accompany
buttons and file selections (Settings → Sound).

## Database viewer (operator maintenance)

A **Database** page browses the platform's own database and lets the operator
**selectively delete** generated records. It lists every table with row counts,
shows a database overview (engine, file/WAL size, journal mode, totals), and
pages through rows with per-row checkboxes to delete the selected rows (or
clear a whole table). Deletions respect SQLite `ON DELETE CASCADE`, so removing
a project/run also removes its samples, variants, candidates and other
children. No arbitrary SQL is executed — only tables from the SQLAlchemy
metadata.

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET    | `/api/database/overview` | Engine, file size, journal mode, totals |
| GET    | `/api/database/tables` | Table names + row counts |
| GET    | `/api/database/tables/{table}` | Paginated rows (`limit`/`offset`) |
| POST   | `/api/database/tables/{table}/delete` | Delete selected rows by id |
| POST   | `/api/database/tables/{table}/clear` | Clear a table |

## Interface

The product is branded **Bravo**. The UI follows an Apple **Liquid Glass**
design language: content-first layout with a translucent, blurred material
system at multiple levels (sidebar / toolbar / panels / buttons), large
continuous corner radii, a scroll-reactive floating top bar, a floating glass
bottom tab bar on small screens, restrained neutral colors with a single accent,
SF-style typography with tabular numerals, and physics-like motion (page
transitions, press spring, pop-in). Both **light and dark** materials are
supported and switchable in **Settings** (persisted), alongside a
**中文 / English** language switch.

## UI guidelines

The interface follows a *Minimal Scientific Research Interface*: white
background, black/dark-grey text, hairline borders, restrained accent color,
~8px radii, and no gradients, glows, 3D, particles, or marketing effects. See
[`docs/ui-guidelines.md`](docs/ui-guidelines.md).

## Testing

```bash
cd backend && pytest
```
