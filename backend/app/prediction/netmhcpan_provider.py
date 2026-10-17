"""NetMHCpan / NetMHCIIpan adapters (licence required).

This is a real adapter: if a NetMHCpan (Class I) or NetMHCIIpan (Class II)
binary is configured (``NETMHCPAN_BIN`` / ``NETMHCIIPAN_BIN``) it runs the tool
and parses its XLS output. Peptides are batched per allele into a single
invocation, the best (lowest %Rank) row is kept per peptide, and the tool
version is detected from the binary itself. When no binary is configured the
provider reports ``UNAVAILABLE`` — it never falls back to the mock provider.

Notes:

- Class I (NetMHCpan): peptides 8–14 aa, alleles ``HLA-A02:01``.
- Class II (NetMHCIIpan): peptides 9–30 aa, alleles ``DRB1_0101`` style
  (``HLA-DRB1*01:01`` is converted).
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
from pathlib import Path

from app.core.config import settings
from app.prediction.base import (
    PredictionInput,
    PredictionOutput,
    PredictionProvider,
    ProviderStatus,
    ProviderUnavailableError,
    ValidationResult,
)
from app.prediction.registry import register_prediction_provider

_STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")


def _netmhc_allele(allele: str) -> str:
    """HLA-A*02:01 -> HLA-A02:01 (the format NetMHCpan expects)."""
    return allele.replace("*", "")


def _netmhciipan_allele(allele: str) -> str:
    """HLA-DRB1*01:01 -> DRB1_0101 (the format NetMHCIIpan expects)."""
    value = allele.strip()
    if value.startswith("HLA-"):
        value = value[4:]
    return value.replace("*", "_").replace(":", "")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _length_flag(provider_kind: str, lengths: set[int]) -> list[str]:
    lengths = sorted(lengths)
    if not lengths:
        return []
    value = ",".join(str(length) for length in lengths)
    # NetMHCpan uses `-l`; NetMHCIIpan uses `-length`.
    return ["-length", value] if provider_kind == "II" else ["-l", value]


class _NetMHCBase(PredictionProvider):
    provider_kind = "I"  # "I" (NetMHCpan) or "II" (NetMHCIIpan)
    binary_setting = "NETMHCPAN_BIN"
    peptide_min = 8
    peptide_max = 14
    allele_converter = staticmethod(_netmhc_allele)

    _version_cache: dict[str, str] = {}

    def _binary(self) -> str:
        return (getattr(settings, self.binary_setting, "") or "").strip()

    def supported_hla(self) -> list[str]:
        return ["*"]

    def _detect_version(self) -> str:
        key = f"{self.provider_name}:{self._binary()}"
        if key in self._version_cache:
            return self._version_cache[key]
        version = f"adapter-{self.provider_version}"
        binary = self._binary()
        if binary:
            for flag in ("-v", "--version"):
                try:
                    completed = subprocess.run(
                        [binary, flag],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    text = (completed.stdout or completed.stderr or "").strip()
                    match = re.search(
                        r"(?:netMHC(?:II)?pan\s+)?version\s*:?\s*([0-9][^\s]*)",
                        text,
                        flags=re.IGNORECASE,
                    )
                    if match:
                        version = f"{self.provider_name} {match.group(1)}"
                        break
                    first = text.splitlines()[0].strip() if text else ""
                    if first and not first.startswith(("usage", "Usage", "-")):
                        version = f"{self.provider_name} {first[:40]}"
                        break
                except Exception:  # noqa: BLE001
                    continue
        self._version_cache[key] = version
        return version

    def health_check(self) -> ProviderStatus:
        path = self._binary()
        if not path:
            return ProviderStatus.UNAVAILABLE
        if not (os.path.isfile(path) and os.access(path, os.X_OK)):
            return ProviderStatus.UNAVAILABLE
        return ProviderStatus.AVAILABLE

    def validate_input(self, inputs: list[PredictionInput]) -> ValidationResult:
        if not inputs:
            return ValidationResult(True)
        for item in inputs:
            if not item.peptide or not (
                self.peptide_min <= len(item.peptide) <= self.peptide_max
            ):
                return ValidationResult(
                    False,
                    f"Unsupported peptide length for {item.candidate_id} "
                    f"({self.provider_name}: {self.peptide_min}-{self.peptide_max} aa)",
                )
            if any(ch not in _STANDARD_AA for ch in item.peptide.upper()):
                return ValidationResult(False, f"Non-standard residue in {item.candidate_id}")
            if not item.hla_allele:
                return ValidationResult(False, f"Missing HLA allele for {item.candidate_id}")
        return ValidationResult(True)

    def predict(self, inputs: list[PredictionInput]) -> list[PredictionOutput]:
        if self.health_check() != ProviderStatus.AVAILABLE:
            raise ProviderUnavailableError(
                f"{self.provider_name} binary is not configured/executable."
            )
        version = self._detect_version()
        grouped: dict[str, list[PredictionInput]] = {}
        for item in inputs:
            grouped.setdefault(item.hla_allele, []).append(item)

        outputs: list[PredictionOutput] = []
        with tempfile.TemporaryDirectory() as tmp:
            for allele, items in grouped.items():
                outputs.extend(self._run_batch(Path(tmp), allele, items, version))
        return outputs

    def _run_batch(
        self,
        tmp: Path,
        allele: str,
        items: list[PredictionInput],
        version: str,
    ) -> list[PredictionOutput]:
        peptide_file = tmp / f"peptides_{_hash(allele)[:8]}.txt"
        peptide_file.write_text("\n".join((item.peptide or "").upper() for item in items) + "\n")

        lengths = {len((item.peptide or "").strip()) for item in items if item.peptide}
        command = [self._binary(), "-p", str(peptide_file), "-a", self.allele_converter(allele)]
        command += _length_flag(self.provider_kind, lengths)
        command += ["-xls", "-xlsfile", "/dev/stdout"]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except Exception as exc:  # noqa: BLE001 - surface real failure
            raise ProviderUnavailableError(f"{self.provider_name} run failed: {exc}") from exc
        if completed.returncode != 0:
            raise ProviderUnavailableError(
                f"{self.provider_name} exited {completed.returncode}: "
                f"{completed.stderr.strip()[:200]}"
            )

        parsed = _parse_netmhc_xls(completed.stdout, allele)
        outputs: list[PredictionOutput] = []
        for item in items:
            peptide = (item.peptide or "").upper()
            rank, detail = parsed.get(peptide, (None, {"parsed": False, "reason": "no data row"}))
            outputs.append(
                PredictionOutput(
                    candidate_id=item.candidate_id,
                    hla=item.hla_allele,
                    prediction_value=rank,
                    metric_name=f"{self.provider_name}_rank",
                    status=ProviderStatus.AVAILABLE.value,
                    provider=self.provider_name,
                    provider_version=version,
                    input_hash=_hash(self.provider_name, item.candidate_id, peptide, item.hla_allele),
                    detail=detail,
                )
            )
        return outputs


def _parse_netmhc_xls(text: str, allele: str) -> dict[str, tuple[float | None, dict]]:
    """Best-effort parse of NetMHCpan/NetMHCIIpan XLS output (header-driven).

    Returns ``{peptide: (best_rank, detail)}`` — the best (lowest %Rank_EL,
    falling back to %Rank_BA) row per peptide across all predicted lengths.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    header_idx = None
    for i, ln in enumerate(lines):
        if "Peptide" in ln and ("%Rank" in ln or "Rank" in ln):
            header_idx = i
            break
    if header_idx is None:
        return {}
    header = re.split(r"\s+", lines[header_idx].strip())
    best: dict[str, tuple[float | None, dict]] = {}

    def rank_of(row: dict) -> float | None:
        for key in ("%Rank_EL", "%Rank_BA", "Rank"):
            value = row.get(key)
            if value is None or value == "-":
                continue
            try:
                return float(value)
            except ValueError:
                continue
        return None

    for ln in lines[header_idx + 1 :]:
        cols = re.split(r"\s+", ln.strip())
        if len(cols) != len(header):
            continue
        row = dict(zip(header, cols))
        peptide = (row.get("Peptide") or "").upper()
        if not peptide or peptide == "-":
            continue
        rank = rank_of(row)
        detail = {
            "parsed": True,
            "allele": allele,
            "rank": rank,
            "score": row.get("Score_EL") or row.get("Score_BA") or row.get("Score"),
            "peptide": peptide,
            "length": row.get("Of"),
        }
        previous = best.get(peptide)
        if previous is None or (rank is not None and (previous[0] is None or rank < previous[0])):
            best[peptide] = (rank, detail)
    return best


@register_prediction_provider
class NetMHCpanProvider(_NetMHCBase):
    provider_kind = "I"
    provider_name = "netmhcpan"
    provider_version = "adapter-1.0"
    is_mock = False
    binary_setting = "NETMHCPAN_BIN"
    peptide_min = 8
    peptide_max = 14
    allele_converter = staticmethod(_netmhc_allele)
    description = "NetMHCpan (Class I) adapter — requires a licensed binary."


@register_prediction_provider
class NetMHCIIpanProvider(_NetMHCBase):
    provider_kind = "II"
    provider_name = "netmhciipan"
    provider_version = "adapter-1.0"
    is_mock = False
    binary_setting = "NETMHCIIPAN_BIN"
    peptide_min = 9
    peptide_max = 30
    allele_converter = staticmethod(_netmhciipan_allele)
    description = "NetMHCIIpan (Class II) adapter — requires a licensed binary."
