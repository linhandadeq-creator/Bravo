# Sequence design engine (global multi-objective)

The construct sequence is produced by a constraint **and objective** engine
(`app/blueprint/`). All scores are transparent, reproducible and labelled
(`heuristic` vs `trained_ridge`) — never fabricated.

## Objectives (simultaneous)

- **Codon usage**: CAI (human-preferred codons) + **tAI** (tRNA adaptation
  index, dos Reis et al. 2004 human weights).
- **Constraints**: GC window (hard 30–70%, target 40–60%), no homopolymer ≥ 6,
  no direct repeat ≥ 12 bp, no restriction sites, no cryptic poly(A)/splice
  motifs, no immunostimulatory motifs.
- **Structure**: 5' window MFE and a bounded **whole-transcript** MFE/nt
  refinement (ViennaRNA).
- Search: **simulated annealing** (multi-seed, deterministic) over synonymous
  codons, followed by deterministic repair/restore passes.

## UTRs

- **5' UTR**: generative — de-novo ATG-free, motif/homopolymer/GC-filtered
  candidates are scored by the translation-efficiency model (trained on MPRA
  when available) and the best of library ∪ generated is used.
- **3' UTR**: dedicated `app/blueprint/stability.py` model (ARE motifs, GC, AU,
  length, structure) picks the most stability-friendly 3' UTR from a library ∪
  generated candidates.

## Predicted-expression & immunogenicity

- **Expression score** (0–100), documented: CAI (25) + tAI (15) + 5' structure
  openness (20) + 5'UTR model (20) + stability (20).
- **Innate-immunity score** (`app/blueprint/immunogenicity.py`, 0–1 lower is
  better): uridine (m1Ψ-scaled) + dsRNA fold-risk (longest inverted-repeat
  stem) + AUUUA + CpG. dsRNA is a structural *fold-risk proxy*, not a trained
  dsRNA model.

All metrics surface in `sequence_qc`, the **production package**
(`sequence_design`, `sequence_qc`) and reports.

## Training the UTR model on MPRA

Two input paths feed the same `sequence,value` format (value = mean ribosome
load):

```bash
# A) author-provided processed table
MPRA_URL=https://.../5utr_mrl.csv.gz python scripts/download_mpra_utr.py
python scripts/train_utr_model.py mpra_utr.csv --holdout 0.2

# B) real GEO 5' UTR MRL library (used in this build):
#    ProtRNA record -> data_mrl.zip -> GSM4084997_varying_length_25to100.csv.gz
python scripts/prepare_mpra_training.py GEO_mrl.csv.gz utr_train.csv.gz --split all
python scripts/train_utr_model.py utr_train.csv.gz 1.0 --holdout 0.2
```

The shipped model was retrained on **85,224 real 5' UTR sequences** (GEO
GSM4084997, varied length 25–100; deterministic 80/20 holdout): **R²(holdout)
= 0.326** (`storage/models/utr_model.json`, `model="trained_ridge"`). The prior
215-row ridge is kept at `storage/models/utr_model_215.json.bak`. Without any
trained weights the platform falls back to a documented heuristic and reports
`model="heuristic"`. GEO GSE114063 (Sample et al. 2019) ships only a 27 GB
BigWig RAW archive; use a processed per-sequence table or the GEO path above.

## Codon-level objectives (stability + codon pairs)

Beyond CAI/tAI the engine now optimises two codon-level objectives
(`app/blueprint/codon_metrics.py`), both **table-replaceable**:

- `codon_stability` (0–1): usage-based stability proxy, normalised so 1.0 =
  all-optimal codons. Drop a published CSC table at
  `storage/models/codon_stability.json` (`{"csc": {"CTG": 0.93, ...}}`).
- `codon_pair_score` (0–1): 1 − fraction of adjacent rare–rare codon pairs.
  Drop a CPS table at `storage/models/codon_pairs.json`
  (`{"pairs": {"CTGCTG": 0.31, ...}}`).

Provenance is reported as `proxy_*` until a table is installed
(`model_info()`), and both metrics surface in the package and sequence QC.

## IVT start + poly(A) design

- `ivt_start` — T7 initiation check (transparent rule): G at +1 preferred,
  pyrimidine +2 penalised; score + notes in package and QC metrics.
- `poly_a_design` — evaluates tail options (60/80/100/120/150 nt) with the
  stability model, reports the recommended length, and flags a segmented
  A40+A20+A40 option (export-level design, not synthesised here).

## Polyepitope assembly (junction safety)

`app/blueprint/assembly.py` + `POST /api/blueprint/assembly`:

- linkers: `AAY` / `GPGPG` / `GGGGS` (G4S) / `KK` / none
- ordering: `input` / `immunogenicity` / `coverage` (greedy HLA union
  coverage) / `junction` (greedy, deterministic — minimises junction windows
  that are self-similar or duplicated)
- junction audit: every 8–11mer window spanning a junction is checked against
  the real human self-proteome index; with `predict_binding=true` + HLA list
  the windows are scored with MHCflurry (unavailable providers are reported,
  never mocked)
- `design=true` runs the full codon/structure engine on the assembled protein
  and returns the new metrics


## Real prediction benchmark

A real binder/non-binder benchmark is built from shipped IEDB mass-spectrometry
ligands (positives) plus shuffled decoys (negatives), deterministically:

```bash
python scripts/build_real_benchmark.py 400        # -> benchmark_small.tsv
python scripts/benchmark_predictors.py benchmark_small.tsv --providers mhcflurry,mixmhcpred,panel
```

Measured AUROC on real data (345 positives / 345 decoys): **MHCflurry 0.928**,
**MixMHCpred 0.915**, **panel 0.928**. PRIME is an immunogenicity (TCR-facing)
model, not a presentation predictor, so it is excluded from the binding
benchmark.

