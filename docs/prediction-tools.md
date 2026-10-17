# Licensed predictors: NetMHCpan / NetMHCIIpan

The platform ships full adapters for the DTU NetMHCpan (Class I) and
NetMHCIIpan (Class II) predictors. The binaries are **not redistributable** —
they require a free academic licence from DTU Health Tech
(https://services.healthtech.dtu.dk).

## Setup

```bash
./scripts/setup_netmhcpan.sh /path/to/netMHCpan /path/to/netMHCIIpan
```

writes `NETMHCPAN_BIN` / `NETMHCIIPAN_BIN` to `backend/.env`; restart the
platform afterwards. Until configured, both providers report `UNAVAILABLE`
and are never replaced by the mock provider.

## Adapter behaviour

- **Batch invocation**: peptides are grouped by HLA allele; each group runs
  in a single tool invocation (one temp file, `-xls -xlsfile` output).
- **Class I vs Class II**:
  - NetMHCpan: 8–14 aa peptides, allele `HLA-A*02:01` → `HLA-A02:01`,
    length flag `-l`.
  - NetMHCIIpan: 9–30 aa peptides, allele `HLA-DRB1*01:01` → `DRB1_0101`,
    length flag `-length`.
  - Out-of-range peptides are rejected at validation time (never sent to the
    tool); the mock provider is never substituted.
- **Best-row selection**: the tool emits one row per predicted length; the
  adapter keeps the row with the lowest `%Rank_EL` (fallback `%Rank_BA`) per
  peptide and records the chosen length.
- **Version detection**: the adapter runs `-v`/`--version` once and stamps
  the reported tool version into every `PredictionResult` (falls back to the
  adapter version).
- **Failure is explicit**: nonzero exit, missing binary or unparseable output
  raises `ProviderUnavailableError` and the pipeline reports the error.

## Verification without a licence

`tests/test_netmhcpan_adapter.py` runs deterministic fake binaries through
the full adapter path (batch, flags, allele conversion, parsing, version
detection, failure surfacing) so the integration is CI-verifiable without
the licensed tools.

## PRIME immunogenicity (TCR-facing)

PRIME 1.0 (GfellerLab) predicts peptide–MHC-I immunogenicity — a complementary
signal to binding/presentation.

```bash
git clone https://github.com/GfellerLab/PRIME.git backend/.venv-prime/PRIME
# download the trained models into backend/.venv-prime/PRIME/models
# (see the PRIME repository; models.tar.gz from the releases page)
```

Then set in `backend/.env`:

```
PRIME_DIR=backend/.venv-prime/PRIME
PRIME_PYTHON=backend/.venv-prime/bin/python
```

The provider reports `AVAILABLE` only when `PRIME_DIR/models` exists. Output
metric: `immunogenicity_score` (0–1, higher = more immunogenic).

## MixMHCpred (Class I binding)

```bash
uv venv --python 3.11 backend/.venv-mix
uv pip install --python backend/.venv-mix/bin/python mixmhcpred
backend/.venv-mix/bin/python -c "from mixmhcpred import predict; predict(['HLA-A*02:01'], ['AAAAAAAAA'])"
```

Set `MIXMHCPRED_PYTHON=backend/.venv-mix/bin/python`. Output metric:
`mixmhcpred_score` (higher = better binder).

## Consensus ensemble

The `consensus` provider now folds in MixMHCpred (Class I binding) and PRIME
(immunogenicity) alongside MHCflurry / MHCnuggets / NetMHCpan / NetMHCIIpan
when configured — more members, tighter ensemble.

## Benchmark harness (AUROC)

```bash
python scripts/benchmark_predictors.py <dataset.tsv> --providers mhcflurry,consensus,panel,mixmhcpred,prime
```

Input columns: `peptide, hla, label` (1 = binder/immunogenic, 0 = decoy). Use
the IEDB weekly benchmark or a curated immunogenicity set to measure each
provider's AUROC reproducibly (`app/prediction/benchmark.py`).

## NetChop (proteasomal cleavage)

NetChop 3.1 predicts per-position proteasomal cleavage (processing chain).
Download the NetChop package (DTU, license agreement) and set:

```
NETCHOP_DIR=backend/.venv-netchop/netchop-3.1
```

Output metric: `cleavage_score` (max per-position cleavage probability).

## MixMHCpred (Class I, free)

```bash
git clone https://github.com/GfellerLab/MixMHCpred backend/external/MixMHCpred
# deps into the venv: numpy pandas scipy matplotlib logomaker (+ mafft for new alleles)
```
Set `MIXMHCPRED_PYTHON=<venv>/bin/python` and
`MIXMHCPRED_TOOL=backend/external/MixMHCpred/MixMHCpred`. Metric:
`mixmhcpred_score` = 100 − %Rank (higher = better binder).

## PRIME 2.1 (immunogenicity, free for academia)

```bash
git clone https://github.com/GfellerLab/PRIME backend/external/PRIME
```
Set `PRIME_DIR=backend/external/PRIME` and `PRIME_PYTHON=<venv>/bin/python`.
PRIME 2.1 requires MixMHCpred v3 in the same environment. Metric:
`immunogenicity_score` (PRIME `Score_bestAllele`). Only alleles present in
`lib/alleles_mapping.txt` are scored; others return no score (never a mock).

## NetMHCpan / NetMHCIIpan / NetChop (DTU license — user action)

These require a one-time free academic license accepted on the DTU site (name +
email + affiliation); the download link is then generated behind `sw_shipped`.

- NetMHCpan 4.2: https://services.healthtech.dtu.dk/services/NetMHCpan-4.2/
  (pick `Darwin_arm64` on Apple Silicon)
- NetMHCIIpan 4.3: https://services.healthtech.dtu.dk/services/NetMHCIIpan-4.3/
  (`Darwin_arm64`)
- NetChop 3.1: https://services.healthtech.dtu.dk/services/NetChop-3.1/
  (`Darwin`)

Then: `./scripts/setup_netmhcpan.sh <package> [<IIpan package>]` and restart.
Until configured, each provider reports UNAVAILABLE and is never substituted by
mock results.

## Public benchmark run

```bash
python scripts/download_benchmark.py --source iedb     # IEDB weekly benchmark
# or
python scripts/download_benchmark.py                    # NetMHCpan annotated benchmark
python scripts/benchmark_predictors.py benchmark.tsv --providers mhcflurry,consensus,panel,mixmhcpred,netchop
```

Reports AUROC per provider (see `app/prediction/benchmark.py`). A ready-made
real benchmark is built from shipped IEDB MS ligands + decoys via
`scripts/build_real_benchmark.py`; measured AUROC (real data): MHCflurry 0.928,
MixMHCpred 0.915 (see `docs/design-engine.md`).

