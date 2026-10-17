"""Tests for the NetMHCpan / NetMHCIIpan adapters with fake binaries.

The real binaries require a DTU licence; these tests run a deterministic
fake executable that emits NetMHCpan-style XLS output, verifying batch
invocation, length flags, allele conversion, best-row selection, version
detection and failure surfacing.
"""
from __future__ import annotations

import os
import stat
import textwrap

import pytest

from app.prediction.base import (
    PredictionInput,
    ProviderStatus,
    ProviderUnavailableError,
)
from app.prediction.netmhcpan_provider import (
    _length_flag,
    _netmhc_allele,
    _netmhciipan_allele,
    _parse_netmhc_xls,
    NetMHCIIpanProvider,
    NetMHCpanProvider,
)

FAKE_BINARY = """#!/usr/bin/env python3
import os
import sys

if len(sys.argv) >= 2 and sys.argv[1] in ("-v", "--version"):
    print("netMHCpan version 4.1b+1 (build date 2023-04-21) DTU Health Tech")
    sys.exit(0)

args = sys.argv[1:]
peptide_file = args[args.index("-p") + 1]
allele = args[args.index("-a") + 1]
log = os.environ.get("FAKE_LOG")
with open(log, "a") as handle:
    handle.write("CALL\\t" + allele + "\\t" + "\\t".join(args) + "\\n")

peptides = [ln.strip() for ln in open(peptide_file) if ln.strip()]
print("# fake NetMHCpan output")
print("Pos MHC Peptide Core Of Score_EL %Rank_EL")
for index, peptide in enumerate(peptides):
    for length in (9, 10):
        rank = round(1.0 + index * 2.5 + (1.0 if length == 10 else 0.0), 2)
        print(f"{1} {allele} {peptide} {peptide} {length} 0.{int(rank * 10):02d} {rank}")
sys.exit(0)
"""


def _make_fake(tmp_path, name="netMHCpan") -> str:
    binary = tmp_path / name
    binary.write_text(FAKE_BINARY)
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    return str(binary)


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


# ---- unit helpers ------------------------------------------------------------


def test_allele_conversions():
    assert _netmhc_allele("HLA-A*02:01") == "HLA-A02:01"
    assert _netmhciipan_allele("HLA-DRB1*01:01") == "DRB1_0101"
    assert _netmhciipan_allele("HLA-DQA1*05:01") == "DQA1_0501"


def test_length_flag_per_kind():
    assert _length_flag("I", {8, 9}) == ["-l", "8,9"]
    assert _length_flag("II", {9, 15}) == ["-length", "9,15"]
    assert _length_flag("II", set()) == []


def test_parse_xls_best_row_and_fallback():
    text = textwrap.dedent(
        """\
        # fake header noise
        Pos MHC Peptide Core Of Score_EL %Rank_EL
        1 HLA-A02:01 AAAAAAAAA AAAAAAAAA 9 0.30 2.00
        2 HLA-A02:01 AAAAAAAAA AAAAAAAAA 10 0.20 1.50
        3 HLA-A02:01 AAAAAAAAAA AAAAAAAAAA 10 0.10 0.80
        """
    )
    parsed = _parse_netmhc_xls(text, "HLA-A02:01")
    assert parsed["AAAAAAAAA"][0] == 1.5
    assert parsed["AAAAAAAAA"][1]["length"] == "10"
    assert parsed["AAAAAAAAAA"][0] == 0.8


def test_parse_xls_rank_ba_fallback():
    text = (
        "Pos MHC Peptide Core Of Score_BA %Rank_BA\n"
        "1 HLA-A02:01 AAAAAAAAA AAAAAAAAA 9 0.30 2.00\n"
    )
    parsed = _parse_netmhc_xls(text, "HLA-A02:01")
    assert parsed["AAAAAAAAA"][0] == 2.0


def test_parse_xls_garbage_returns_empty():
    assert _parse_netmhc_xls("no header here\n", "HLA-A02:01") == {}


# ---- input validation --------------------------------------------------------


def test_class_i_length_validation():
    provider = NetMHCpanProvider()
    ok = provider.validate_input(
        _inputs(("c1", "AAAAAAAA", "HLA-A*02:01"), ("c2", "AAAAAAAAAAAAAA", "HLA-A*02:01"))
    )
    assert ok.ok is True
    bad = provider.validate_input(_inputs(("c3", "AAAAAAA", "HLA-A*02:01")))
    assert bad.ok is False
    bad2 = provider.validate_input(_inputs(("c4", "A" * 15, "HLA-A*02:01")))
    assert bad2.ok is False


def test_class_ii_length_validation():
    provider = NetMHCIIpanProvider()
    ok = provider.validate_input(
        _inputs(
            ("c1", "A" * 9, "HLA-DRB1*01:01"),
            ("c2", "A" * 15, "HLA-DRB1*01:01"),
            ("c3", "A" * 30, "HLA-DRB1*01:01"),
        )
    )
    assert ok.ok is True
    bad = provider.validate_input(_inputs(("c4", "A" * 8, "HLA-DRB1*01:01")))
    assert bad.ok is False
    bad2 = provider.validate_input(_inputs(("c5", "A" * 31, "HLA-DRB1*01:01")))
    assert bad2.ok is False


def test_nonstandard_residue_rejected():
    provider = NetMHCpanProvider()
    result = provider.validate_input(_inputs(("c1", "AAAAABAAA", "HLA-A*02:01")))
    assert result.ok is False


# ---- provider flows with fake binaries ---------------------------------------


def test_batch_prediction_single_invocation(monkeypatch, tmp_path):
    binary = _make_fake(tmp_path)
    log = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setattr("app.prediction.netmhcpan_provider.settings.NETMHCPAN_BIN", binary)

    provider = NetMHCpanProvider()
    assert provider.health_check() == ProviderStatus.AVAILABLE

    outputs = provider.predict(
        _inputs(
            ("c1", "AAAAAAAAA", "HLA-A*02:01"),
            ("c2", "AAAAAAAAAA", "HLA-A*02:01"),
        )
    )
    assert len(outputs) == 2
    by_id = {out.candidate_id: out for out in outputs}
    assert by_id["c1"].prediction_value == 1.0  # index 0, length 9 best
    assert by_id["c2"].prediction_value == 3.5  # index 1, length 9 best
    assert by_id["c1"].metric_name == "netmhcpan_rank"
    assert by_id["c1"].provider_version.startswith("netmhcpan 4.1")
    assert by_id["c1"].detail["parsed"] is True

    calls = log.read_text().strip().splitlines()
    assert len(calls) == 1  # one invocation for the batch
    assert "HLA-A02:01" in calls[0]
    assert "-l" in calls[0]


def test_best_row_per_peptide(monkeypatch, tmp_path):
    binary = _make_fake(tmp_path)
    log = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setattr("app.prediction.netmhcpan_provider.settings.NETMHCPAN_BIN", binary)

    outputs = NetMHCpanProvider().predict(_inputs(("c1", "AAAAAAAAA", "HLA-A*02:01")))
    assert outputs[0].prediction_value == 1.0  # best of 9 (1.0) and 10 (2.0)
    assert outputs[0].detail["length"] == "9"


def test_class_ii_allele_conversion_and_length_flag(monkeypatch, tmp_path):
    binary = _make_fake(tmp_path, name="netMHCIIpan")
    log = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setattr("app.prediction.netmhcpan_provider.settings.NETMHCIIPAN_BIN", binary)

    outputs = NetMHCIIpanProvider().predict(
        _inputs(("c1", "AAAAAAAAAAAAAAAAAAA", "HLA-DRB1*01:01"))
    )
    assert outputs[0].prediction_value is not None
    calls = log.read_text().strip().splitlines()
    assert len(calls) == 1
    assert "DRB1_0101" in calls[0]
    assert "-length" in calls[0]
    assert "19" in calls[0]


def test_groups_by_allele(monkeypatch, tmp_path):
    binary = _make_fake(tmp_path)
    log = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setattr("app.prediction.netmhcpan_provider.settings.NETMHCPAN_BIN", binary)

    outputs = NetMHCpanProvider().predict(
        _inputs(
            ("c1", "AAAAAAAAA", "HLA-A*02:01"),
            ("c2", "AAAAAAAAAA", "HLA-A*01:01"),
        )
    )
    assert len(outputs) == 2
    calls = log.read_text().strip().splitlines()
    assert len(calls) == 2  # one invocation per allele


def test_nonzero_exit_surfaces_failure(monkeypatch, tmp_path):
    binary = tmp_path / "failing"
    binary.write_text("#!/usr/bin/env bash\necho 'boom' >&2\nexit 3\n")
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr("app.prediction.netmhcpan_provider.settings.NETMHCPAN_BIN", str(binary))

    with pytest.raises(ProviderUnavailableError) as excinfo:
        NetMHCpanProvider().predict(_inputs(("c1", "AAAAAAAAA", "HLA-A*02:01")))
    assert "exited 3" in str(excinfo.value)


def test_unavailable_without_binary():
    assert NetMHCpanProvider().health_check() == ProviderStatus.UNAVAILABLE
    assert NetMHCIIpanProvider().health_check() == ProviderStatus.UNAVAILABLE
    with pytest.raises(ProviderUnavailableError):
        NetMHCpanProvider().predict(_inputs(("c1", "AAAAAAAAA", "HLA-A*02:01")))
