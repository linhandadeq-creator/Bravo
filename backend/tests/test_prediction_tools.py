"""Tests for the P1 prediction stack: PRIME / MixMHCpred adapters and the
benchmark AUROC utility."""
from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from app.prediction.base import PredictionInput, ProviderStatus, ProviderUnavailableError
from app.prediction.benchmark import evaluate_provider, roc_auc
from app.prediction.consensus import _MEMBERS
from app.prediction.prime_provider import PrimeImmunogenicityProvider
from app.prediction.mixmhcpred_provider import MixMHCpredProvider
from app.prediction.registry import list_prediction_providers


def _inputs(*candidates):
    return [
        PredictionInput(
            candidate_id=cid,
            peptide=peptide,
            peptide_representation=peptide,
            hla_allele=allele,
        )
        for cid, peptide, allele in candidates
    ]


# ---- roc_auc ----------------------------------------------------------------


def test_roc_auc_perfect_separation():
    assert roc_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0


def test_roc_auc_inverted():
    assert roc_auc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0


def test_roc_auc_mixed_and_ties():
    auc = roc_auc([0, 1, 0, 1], [0.5, 0.5, 0.1, 0.9])
    assert 0.5 <= auc <= 1.0


def test_roc_auc_handles_missing_and_single_class():
    assert roc_auc([0, 1, 0, 1], [0.1, None, 0.3, 0.8]) is not None
    assert roc_auc([1, 1, 1], [0.1, 0.2, 0.3]) is None
    assert roc_auc([], []) is None


# ---- provider registration & members ----------------------------------------


def test_new_providers_registered():
    names = {p["name"] for p in list_prediction_providers()}
    assert {"prime", "mixmhcpred"} <= names
    for p in list_prediction_providers():
        if p["name"] in ("prime", "mixmhcpred"):
            assert p["status"] in ("AVAILABLE", "UNAVAILABLE", "FAILED")
            assert p["is_mock"] is False


def test_consensus_members_include_new_providers():
    assert "prime" in _MEMBERS and "mixmhcpred" in _MEMBERS


# ---- PRIME adapter -----------------------------------------------------------


def test_prime_unavailable_without_config(monkeypatch):
    monkeypatch.setattr("app.prediction.prime_provider.settings.PRIME_DIR", "")
    monkeypatch.setattr("app.prediction.prime_provider.settings.PRIME_PYTHON", "")
    monkeypatch.setattr("app.prediction.prime_provider.settings.PRIME_RUNNER", "")
    provider = PrimeImmunogenicityProvider()
    assert provider.health_check() == ProviderStatus.UNAVAILABLE
    with pytest.raises(ProviderUnavailableError):
        provider.predict(_inputs(("c1", "AAAAAAAAA", "HLA-A*02:01")))


def test_prime_validation_lengths():
    provider = PrimeImmunogenicityProvider()
    assert provider.validate_input(_inputs(("c1", "AAAAAAAAA", "HLA-A*02:01"))).ok is True
    assert provider.validate_input(_inputs(("c2", "AAAAAAAA", "HLA-A*02:01"))).ok is True
    assert provider.validate_input(_inputs(("c3", "AAAAAAA", "HLA-A*02:01"))).ok is False
    assert provider.validate_input(_inputs(("c4", "A" * 15, "HLA-A*02:01"))).ok is False


_FAKE_PRIME = """#!/usr/bin/env python3
import json, sys
req = json.load(open(sys.argv[2]))
results = []
for i, item in enumerate(req["requests"]):
    results.append({"key": item["key"], "immunogenicity": 0.9 if i == 0 else 0.1})
print(json.dumps({"results": results}))
"""


def test_prime_fake_runner_predict(monkeypatch, tmp_path):
    runner = tmp_path / "prime_runner.py"
    runner.write_text(_FAKE_PRIME)
    runner.chmod(runner.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "PRIME").write_text("#!/bin/bash\nexit 0\n")
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "run_PRIME.pl").write_text("# fake")

    monkeypatch.setattr("app.prediction.prime_provider.settings.PRIME_RUNNER", str(runner))
    monkeypatch.setattr("app.prediction.prime_provider.settings.PRIME_DIR", str(tmp_path))
    monkeypatch.setattr("app.prediction.prime_provider.settings.PRIME_PYTHON", "python3")

    provider = PrimeImmunogenicityProvider()
    assert provider.health_check() == ProviderStatus.AVAILABLE
    outputs = provider.predict(
        _inputs(
            ("c1", "AAAAAAAAA", "HLA-A*02:01"),
            ("c2", "CCCCCCCCC", "HLA-A*02:01"),
        )
    )
    by_id = {out.candidate_id: out for out in outputs}
    assert by_id["c1"].prediction_value == 0.9
    assert by_id["c2"].prediction_value == 0.1
    assert by_id["c1"].metric_name == "immunogenicity_score"
    assert by_id["c1"].provider == "prime"


def test_prime_nonzero_exit_surfaces(monkeypatch, tmp_path):
    runner = tmp_path / "prime_runner.py"
    runner.write_text("#!/usr/bin/env python3\nimport sys; sys.exit(4)\n")
    runner.chmod(runner.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "PRIME").write_text("#!/bin/bash\nexit 0\n")
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "run_PRIME.pl").write_text("# fake")
    monkeypatch.setattr("app.prediction.prime_provider.settings.PRIME_RUNNER", str(runner))
    monkeypatch.setattr("app.prediction.prime_provider.settings.PRIME_DIR", str(tmp_path))
    monkeypatch.setattr("app.prediction.prime_provider.settings.PRIME_PYTHON", "python3")

    provider = PrimeImmunogenicityProvider()
    with pytest.raises(ProviderUnavailableError):
        provider.predict(_inputs(("c1", "AAAAAAAAA", "HLA-A*02:01")))


# ---- MixMHCpred adapter ------------------------------------------------------


def test_mixmhcpred_unavailable_without_config(monkeypatch):
    monkeypatch.setattr("app.prediction.mixmhcpred_provider.settings.MIXMHCPRED_PYTHON", "")
    monkeypatch.setattr("app.prediction.mixmhcpred_provider.settings.MIXMHCPRED_RUNNER", "")
    monkeypatch.setattr("app.prediction.mixmhcpred_provider.settings.MIXMHCPRED_TOOL", "")
    provider = MixMHCpredProvider()
    assert provider.health_check() == ProviderStatus.UNAVAILABLE
    with pytest.raises(ProviderUnavailableError):
        provider.predict(_inputs(("c1", "AAAAAAAAA", "HLA-A*02:01")))


_FAKE_MIX = """#!/usr/bin/env python3
import json, sys
req = json.load(open(sys.argv[1]))
results = []
for i, item in enumerate(req["requests"]):
    results.append({"key": item["key"], "score": 0.7 if i == 0 else 0.2})
print(json.dumps({"results": results}))
"""


def test_mixmhcpred_fake_runner_predict(monkeypatch, tmp_path):
    runner = tmp_path / "mix_runner.py"
    runner.write_text(_FAKE_MIX)
    runner.chmod(runner.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(
        "app.prediction.mixmhcpred_provider.settings.MIXMHCPRED_RUNNER", str(runner)
    )
    monkeypatch.setattr(
        "app.prediction.mixmhcpred_provider.settings.MIXMHCPRED_PYTHON", "python3"
    )

    provider = MixMHCpredProvider()
    assert provider.health_check() == ProviderStatus.AVAILABLE
    outputs = provider.predict(
        _inputs(
            ("c1", "AAAAAAAAA", "HLA-A*02:01"),
            ("c2", "CCCCCCCCC", "HLA-A*02:01"),
        )
    )
    by_id = {out.candidate_id: out for out in outputs}
    assert by_id["c1"].prediction_value == 0.7
    assert by_id["c1"].metric_name == "mixmhcpred_score"


def test_mixmhcpred_runner_parses_tool_tsv():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.mixmhcpred_runner import _parse_output

    text = (
        "# Output from MixMHCpred (v3.0)\n"
        "Peptide\tScore_bestAllele\tBestAllele\t%Rank_bestAllele\tScore_A0201\t%Rank_A0201\n"
        "SIINFEKL\t-1.119737\tA0201\t2.698623\t-1.119737\t2.698623\n"
    )
    scores = _parse_output(text)
    assert scores["SIINFEKL"] == pytest.approx(100 - 2.698623, rel=1e-6)


def test_prime_runner_parses_tool_tsv():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.prime_runner import _parse_output

    text = (
        "# Output from PRIME (v2.1)\n"
        "Peptide\t%Rank_bestAllele\tScore_bestAllele\t%RankBinding_bestAllele\tBestAllele\n"
        "SLLPAIVEL\t0.004\t0.272185\t0.002\tA0201\n"
    )
    scores = _parse_output(text)
    assert scores["SLLPAIVEL"] == pytest.approx(0.272185, rel=1e-6)


# ---- benchmark harness -------------------------------------------------------


def test_evaluate_provider_reports_auc_for_mock():
    from app.prediction.registry import get_prediction_provider

    rows = [
        {"peptide": "MEGFPAAAA", "hla": "HLA-A*02:01", "label": 1},
        {"peptide": "MSGKFAAAA", "hla": "HLA-A*02:01", "label": 1},
        {"peptide": "VVVGADGVGK", "hla": "HLA-A*02:01", "label": 0},
        {"peptide": "EAAPHVAPA", "hla": "HLA-A*02:01", "label": 0},
    ]
    provider = get_prediction_provider("mock")
    result = evaluate_provider(provider, rows)
    assert result.available is True
    assert result.n_evaluated == 4
    assert result.auc is None or 0.0 <= result.auc <= 1.0


# ---- NetChop adapter ---------------------------------------------------------


def test_netchop_registered_and_unavailable_without_config():
    from app.prediction.netchop_provider import NetChopProvider

    names = {p["name"] for p in list_prediction_providers()}
    assert "netchop" in names
    provider = NetChopProvider()
    assert provider.health_check() == ProviderStatus.UNAVAILABLE
    with pytest.raises(ProviderUnavailableError):
        provider.predict(_inputs(("c1", "AAAAAAAAA", "HLA-A*02:01")))


_FAKE_NETCHOP = """#!/usr/bin/env python3
import json, sys
req = json.load(open(sys.argv[2]))
results = []
for i, item in enumerate(req["requests"]):
    results.append({"key": item["key"], "cleavage": 0.81 if i == 0 else 0.11})
print(json.dumps({"results": results}))
"""


def test_netchop_fake_runner_predict(monkeypatch, tmp_path):
    from app.prediction.netchop_provider import NetChopProvider

    runner = tmp_path / "netchop_runner.py"
    runner.write_text(_FAKE_NETCHOP)
    runner.chmod(runner.stat().st_mode | stat.S_IEXEC)
    binary = tmp_path / "netchop"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setattr(
        "app.prediction.netchop_provider.settings.NETCHOP_RUNNER", str(runner)
    )
    monkeypatch.setattr(
        "app.prediction.netchop_provider.settings.NETCHOP_DIR", str(tmp_path)
    )

    provider = NetChopProvider()
    assert provider.health_check() == ProviderStatus.AVAILABLE
    outputs = provider.predict(
        _inputs(
            ("c1", "AAAAAAAAA", "HLA-A*02:01"),
            ("c2", "CCCCCCCCC", "HLA-A*02:01"),
        )
    )
    by_id = {out.candidate_id: out for out in outputs}
    assert by_id["c1"].prediction_value == 0.81
    assert by_id["c1"].metric_name == "cleavage_score"
    assert by_id["c1"].provider == "netchop"


def test_netchop_parser_max_position():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "netchop_runner",
        Path(__file__).resolve().parents[2] / "scripts" / "netchop_runner.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    text = (
        "0 sequence PEP1\n"
        "   0  A  S  0.12\n"
        "   1  A  S  0.55\n"
        "----\n"
        "0 sequence PEP2\n"
        "   0  C  S  0.20\n"
    )
    scores = module.parse_netchop(text)
    assert scores == {"PEP1": 0.55, "PEP2": 0.20}


# ---- consensus auto-includes NetMHCpan once a binary is configured ----------

_FAKE_NETMHCPAN = """#!/usr/bin/env python3
import sys
if len(sys.argv) >= 2 and sys.argv[1] in ("-v", "--version"):
    print("netMHCpan version 4.1b+1 (build date 2023-04-21) DTU Health Tech")
    sys.exit(0)
args = sys.argv[1:]
peptide_file = args[args.index("-p") + 1]
allele = args[args.index("-a") + 1]
peptides = [ln.strip() for ln in open(peptide_file) if ln.strip()]
print("Pos MHC Peptide Core Of Score_EL %Rank_EL")
for index, peptide in enumerate(peptides):
    print(f"1 {allele} {peptide} {peptide} 9 0.5 {index + 1.0}")
sys.exit(0)
"""


def test_consensus_auto_includes_netmhcpan_when_configured(monkeypatch, tmp_path):
    """After installing the licensed binary, NetMHCpan must join the
    consensus ensemble automatically (documented 'auto-join' behaviour)."""
    from app.prediction.registry import get_prediction_provider

    binary = tmp_path / "netMHCpan"
    binary.write_text(_FAKE_NETMHCPAN)
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(
        "app.prediction.netmhcpan_provider.settings.NETMHCPAN_BIN", str(binary)
    )

    consensus = get_prediction_provider("consensus")
    outputs = consensus.predict(
        _inputs(
            ("c1", "AAAAAAAAA", "HLA-A*02:01"),
            ("c2", "CCCCCCCCC", "HLA-A*02:01"),
            ("c3", "DDDDDDDDD", "HLA-A*02:01"),
        )
    )
    assert outputs, "consensus produced no outputs"
    providers = set()
    for out in outputs:
        providers |= set((out.detail or {}).get("providers", {}).keys())
    assert "netmhcpan" in providers, "NetMHCpan did not join the consensus"
