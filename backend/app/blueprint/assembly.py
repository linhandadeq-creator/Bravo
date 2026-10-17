"""Polyepitope assembly: ordering, linkers and junction safety analysis.

Mainstream mRNA-vaccine dry-lab pipelines concatenate epitopes with linkers
(AAY / GPGPG / GGGGS) and must control what the junctions create: novel HLA
binders, self-similar peptides and processing-hostile stretches. This module
implements the assembly and the junction audit on top of the design engine:

- linkers: AAY / GPGPG / GGGGS / KK / none
- ordering: ``input`` / ``immunogenicity`` / ``coverage`` (greedy HLA union
  coverage) / ``junction`` (greedy, deterministic; minimises junction windows
  that are self-similar or duplicated inside the construct)
- junction audit: every 8–11mer window spanning a junction is checked against
  the real human self-proteome index (when installed); optional HLA binding of
  those windows via the platform prediction registry (opt-in — unavailable
  providers are reported, never mocked).

Research use only: junction flags require wet-lab confirmation.
"""
from __future__ import annotations

WINDOW_SIZES = (8, 9, 10, 11)
LINKERS: dict[str, str] = {
    "AAY": "AAY",
    "GPGPG": "GPGPG",
    "G4S": "GGGGS",
    "KK": "KK",
    "none": "",
}
STRATEGIES = ("input", "immunogenicity", "coverage", "junction")
_STANDARD = set("ACDEFGHIKLMNPQRSTVWY")


def _clean(epitopes: list[dict]) -> list[dict]:
    cleaned = []
    for index, item in enumerate(epitopes):
        peptide = str(item.get("peptide", "")).upper().strip()
        if not peptide or any(ch not in _STANDARD for ch in peptide):
            raise ValueError(f"invalid peptide for epitope #{index + 1}: {peptide!r}")
        cleaned.append({**item, "peptide": peptide})
    if not cleaned:
        raise ValueError("at least one epitope is required")
    return cleaned


def build_protein(epitopes: list[str], linker: str) -> tuple[str, list[int]]:
    """Concatenate epitopes with ``linker``; return protein + junction offsets.

    A junction offset is the index of the first residue after an epitope
    (i.e. the boundary that the linker / next epitope crosses).
    """
    junctions: list[int] = []
    protein = ""
    for index, peptide in enumerate(epitopes):
        protein += peptide
        if index < len(epitopes) - 1:
            junctions.append(len(protein))
            protein += linker
    return protein, junctions


def junction_windows(protein: str, boundary: int) -> list[str]:
    """All standard 8–11mer windows that strictly span ``boundary``."""
    windows: list[str] = []
    seen: set[str] = set()
    for size in WINDOW_SIZES:
        for start in range(max(0, boundary - size + 1), min(boundary, len(protein) - size) + 1):
            window = protein[start : start + size]
            if window in seen or len(window) != size:
                continue
            if any(ch not in _STANDARD for ch in window):
                continue
            seen.add(window)
            windows.append(window)
    return windows


def _self_hits(windows: list[str]) -> list[str]:
    try:
        from app.services.self_filter import is_available, is_self_similar

        if not is_available():
            return []
        return [w for w in windows if is_self_similar(w)]
    except Exception:  # noqa: BLE001
        return []


def _duplicate_hits(protein: str, windows: list[str]) -> list[str]:
    hits = []
    for window in windows:
        first = protein.find(window)
        if first != -1 and protein.find(window, first + 1) != -1:
            hits.append(window)
    return hits


def _junction_risk(protein: str, junctions: list[int]) -> tuple[int, int]:
    self_count = 0
    dup_count = 0
    for boundary in junctions:
        windows = junction_windows(protein, boundary)
        self_count += len(_self_hits(windows))
        dup_count += len(_duplicate_hits(protein, windows))
    return self_count, dup_count


def order_epitopes(epitopes: list[dict], strategy: str, linker: str) -> list[dict]:
    """Deterministically order epitopes for assembly."""
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; choose from {STRATEGIES}")

    if strategy == "input":
        return list(epitopes)
    if strategy == "immunogenicity":
        return sorted(
            epitopes,
            key=lambda item: (-float(item.get("score") or 0.0), item["peptide"]),
        )
    if strategy == "coverage":
        from app.services.population_coverage import estimate

        remaining = list(epitopes)
        ordered: list[dict] = []
        while remaining:
            best = None
            best_coverage = -1.0
            for candidate in remaining:
                trial = ordered + [candidate]
                alleles = [str(item.get("hla") or "") for item in trial]
                coverage = estimate([a for a in alleles if a]).get(
                    "overall_coverage", 0.0
                )
                if coverage > best_coverage:
                    best_coverage = coverage
                    best = candidate
            ordered.append(best)  # type: ignore[arg-type]
            remaining.remove(best)  # type: ignore[arg-type]
        return ordered

    remaining = list(epitopes)
    ordered = [remaining.pop(0)]
    while remaining:
        best = None
        best_risk = None
        for candidate in remaining:
            trial = ordered + [candidate]
            protein, junctions = build_protein(
                [item["peptide"] for item in trial], linker
            )
            risk = _junction_risk(protein, junctions)
            if best_risk is None or risk < best_risk:
                best_risk = risk
                best = candidate
        ordered.append(best)  # type: ignore[arg-type]
        remaining.remove(best)  # type: ignore[arg-type]
    return ordered


def analyze_junctions(
    protein: str,
    junctions: list[int],
    *,
    predict_binding: bool = False,
    hla: list[str] | None = None,
) -> dict:
    entries = []
    for boundary in junctions:
        windows = junction_windows(protein, boundary)
        entry = {
            "position": boundary,
            "windows": windows,
            "self_similar": _self_hits(windows),
            "duplicated": _duplicate_hits(protein, windows),
        }
        entries.append(entry)

    report = {
        "n_junctions": len(junctions),
        "windows_checked": sum(len(e["windows"]) for e in entries),
        "self_similar_count": sum(len(e["self_similar"]) for e in entries),
        "duplicated_count": sum(len(e["duplicated"]) for e in entries),
        "self_filter": _self_filter_status(),
        "binding": None,
        "junctions": entries,
    }
    if predict_binding:
        report["binding"] = _binding_scan(entries, hla or [])
    return report


def _self_filter_status() -> dict:
    try:
        from app.services.self_filter import status

        return status()
    except Exception:  # noqa: BLE001
        return {"available": False}


def _binding_scan(entries: list[dict], hla: list[str]) -> dict:
    if not hla:
        return {"status": "skipped", "reason": "no HLA alleles provided"}
    try:
        from app.prediction.base import PredictionInput, ProviderStatus
        from app.prediction.registry import get_prediction_provider

        provider = get_prediction_provider("mhcflurry")
        if provider.health_check() != ProviderStatus.AVAILABLE:
            return {"status": "skipped", "reason": "mhcflurry unavailable"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "skipped", "reason": f"registry error: {exc}"}

    inputs = []
    keyed: dict[str, tuple[int, str, str]] = {}
    for entry_index, entry in enumerate(entries):
        for window in entry["windows"]:
            for allele in hla:
                key = f"j{entry_index}:{window}:{allele}"
                keyed[key] = (entry_index, window, allele)
                inputs.append(
                    PredictionInput(
                        candidate_id=key,
                        peptide=window,
                        peptide_representation=window,
                        hla_allele=allele,
                    )
                )
    try:
        outputs = provider.predict(inputs)
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "reason": str(exc)[:200]}

    best_by_junction: dict[int, dict] = {}
    for out in outputs:
        entry_index, window, allele = keyed[out.candidate_id]
        value = out.prediction_value
        if value is None:
            continue
        current = best_by_junction.get(entry_index)
        if current is None or value > current["value"]:
            best_by_junction[entry_index] = {
                "window": window,
                "hla": allele,
                "value": value,
                "metric": out.metric_name,
            }
    for entry_index, best in best_by_junction.items():
        entries[entry_index]["top_binding"] = best
    return {
        "status": "ok",
        "provider": "mhcflurry",
        "n_scored": len(outputs),
        "note": "Junction windows with high presentation scores are novel-epitope risks.",
    }


def assemble(
    epitopes: list[dict],
    *,
    linker: str = "GPGPG",
    strategy: str = "junction",
    predict_binding: bool = False,
    hla: list[str] | None = None,
    design: bool = False,
) -> dict:
    """Assemble a polyepitope protein; audit junctions; optionally design it."""
    cleaned = _clean(epitopes)
    if linker not in LINKERS:
        raise ValueError(f"unknown linker {linker!r}; choose from {sorted(LINKERS)}")
    linker_seq = LINKERS[linker]

    ordered = order_epitopes(cleaned, strategy, linker_seq)
    protein, junctions = build_protein([item["peptide"] for item in ordered], linker_seq)
    if len(protein) > 4000:
        raise ValueError(f"assembled protein too long ({len(protein)} aa; max 4000)")

    report = analyze_junctions(
        protein, junctions, predict_binding=predict_binding, hla=hla
    )
    result: dict = {
        "protein": protein,
        "length": len(protein),
        "linker": linker,
        "linker_sequence": linker_seq,
        "strategy": strategy,
        "epitopes": [
            {"peptide": item["peptide"], "hla": item.get("hla"), "score": item.get("score")}
            for item in ordered
        ],
        "junctions": junctions,
        "report": report,
    }
    if design:
        from app.blueprint.design import DesignConfig, design_construct

        designed = design_construct([protein], DesignConfig())
        result["design"] = {
            "dna_length": len(designed.dna),
            "gc_percent": designed.gc_percent,
            "cai": designed.cai,
            "tai": designed.tai,
            "codon_stability": designed.codon_stability,
            "codon_pair_score": designed.codon_pair_score,
            "codon_metrics_model": designed.codon_metrics_model,
            "expression_score": designed.expression_score,
            "stability_score": designed.stability_score,
            "ivt_start": designed.ivt_start,
            "poly_a_design": designed.poly_a_design,
            "constraints_ok": designed.constraints_ok,
        }
    return result
