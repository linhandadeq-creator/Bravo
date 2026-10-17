"""Ensembl VEP provider — real annotation via the Ensembl VEP REST API.

Uses the official Ensembl REST VEP endpoint (GRCh38 / GRCh37) to obtain the real
gene, transcript, consequence, impact, protein change and positions, and fetches
the reference CDS from Ensembl to build a real mutant peptide. It never falls
back to the mock annotator; failures are reported as FAILED/UNAVAILABLE.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from app.annotation.base import (
    AnnotationRecord,
    AnnotationStatus,
    Consequence,
    Impact,
    ProviderMetadata,
    ProviderUnavailableError,
    ReferenceContext,
    VariantAnnotator,
    VariantInput,
)
from app.annotation.registry import register
from app.core.config import settings
from app.core.reference import GRCH37, GRCH38

_BASE_URLS = {
    GRCH38: "https://rest.ensembl.org",
    GRCH37: "https://grch37.rest.ensembl.org",
}
_TIMEOUT = 45.0

_CONSEQUENCE_MAP = [
    ("stop_gained", Consequence.STOP_GAINED.value, Impact.HIGH.value),
    ("stop_lost", Consequence.STOP_LOST.value, Impact.HIGH.value),
    ("start_lost", Consequence.START_LOST.value, Impact.HIGH.value),
    ("frameshift_variant", Consequence.FRAMESHIFT.value, Impact.HIGH.value),
    ("splice_acceptor_variant", Consequence.SPLICE_RELATED.value, Impact.HIGH.value),
    ("splice_donor_variant", Consequence.SPLICE_RELATED.value, Impact.HIGH.value),
    ("splice_region_variant", Consequence.SPLICE_RELATED.value, Impact.HIGH.value),
    ("inframe_insertion", Consequence.INFRAME_INSERTION.value, Impact.MODERATE.value),
    ("inframe_deletion", Consequence.INFRAME_DELETION.value, Impact.MODERATE.value),
    ("missense_variant", Consequence.MISSENSE.value, Impact.MODERATE.value),
    ("synonymous_variant", Consequence.SYNONYMOUS.value, Impact.LOW.value),
]

_SEVERITY = {
    Consequence.STOP_GAINED.value: 6,
    Consequence.STOP_LOST.value: 6,
    Consequence.START_LOST.value: 6,
    Consequence.FRAMESHIFT.value: 5,
    Consequence.SPLICE_RELATED.value: 5,
    Consequence.MISSENSE.value: 4,
    Consequence.INFRAME_INSERTION.value: 3,
    Consequence.INFRAME_DELETION.value: 3,
    Consequence.SYNONYMOUS.value: 2,
    Consequence.UNKNOWN.value: 0,
}

_CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}
_STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")

_release_cache: dict[str, tuple[str, float]] = {}
_available_cache: dict[str, tuple[bool, float]] = {}


def _base(reference_build: str | None) -> str:
    return _BASE_URLS.get(reference_build or GRCH38, _BASE_URLS[GRCH38])


def _ensembl_release(base: str) -> str:
    cached = _release_cache.get(base)
    if cached:
        value, ts = cached
        # Real release: cache 1 hour. Fallback string: retry after 10 minutes.
        if (time.time() - ts) < (3600.0 if value != "Ensembl REST" else 600.0):
            return value
    release = "Ensembl REST"
    try:
        # Bounded: never block the provider list for long on a slow service.
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(
                f"{base}/info/software", headers={"Accept": "application/json"}
            )
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith(
                "application/json"
            ):
                release = str(resp.json().get("release", release))
    except Exception:  # noqa: BLE001
        pass
    _release_cache[base] = (release, time.time())
    return release


def _is_available(reference_build: str | None) -> bool:
    base = _base(reference_build)
    cached = _available_cache.get(base)
    if cached:
        ok, ts = cached
        # Healthy result cached for 5 minutes; a failure only briefly, so a
        # transient Ensembl blip recovers quickly instead of hiding VEP.
        if (time.time() - ts) < (300.0 if ok else 45.0):
            return ok

    import socket
    from urllib.parse import urlparse

    host = urlparse(base).hostname or "rest.ensembl.org"
    ok = False
    network_error = False
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(
                f"{base}/info/ping", params={"content-type": "application/json"}
            )
        ok = resp.status_code == 200
    except Exception:  # noqa: BLE001 - transient network error
        network_error = True

    # A non-200 means the service is degraded and is reported unavailable. Only
    # a *network* failure falls back to a fast TCP reachability probe (the ping
    # endpoint can be slow even when the service is up).
    if not ok and network_error:
        try:
            with socket.create_connection((host, 443), timeout=4):
                ok = True
        except OSError:
            ok = False

    _available_cache[base] = (ok, time.time())
    return ok


def _cache_file(reference_build: str, variant: VariantInput) -> Path:
    directory = settings.storage_path / "vep_cache" / reference_build
    directory.mkdir(parents=True, exist_ok=True)
    chrom = (variant.chromosome or "").replace("chr", "")
    name = f"{chrom}_{variant.position}_{variant.reference}_{variant.alternate}.json"
    return directory / name


def _read_cache(reference_build: str, variant: VariantInput) -> dict | None:
    path = _cache_file(reference_build, variant)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            return None
    return None


def _write_cache(reference_build: str, variant: VariantInput, entry: dict) -> None:
    try:
        _cache_file(reference_build, variant).write_text(json.dumps(entry))
    except Exception:  # noqa: BLE001
        pass


def _post_vep(client: httpx.Client, base: str, chunk: list[str]) -> httpx.Response:
    last = "unknown error"
    for attempt in range(4):
        try:
            response = client.post(
                f"{base}/vep/human/region",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "variants": chunk,
                    # Request MANE Select / canonical transcripts so the reported
                    # protein change matches the agreed reference (e.g. BRAF
                    # p.V600E, not a longer isoform's p.V640E).
                    "mane": 1,
                    "canonical": 1,
                    "hgvs": 1,
                    "protein": 1,
                    "symbol": 1,
                },
                timeout=90.0,
            )
            if response.status_code == 200:
                return response
            last = f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(2 * (attempt + 1))
    raise ProviderUnavailableError(f"VEP REST request failed after retries: {last}")


def _translate(cds: str) -> str:
    protein = []
    for i in range(0, len(cds) - 2, 3):
        codon = cds[i : i + 3].upper()
        residue = _CODON_TABLE.get(codon, "X")
        if residue == "*":
            break
        protein.append(residue)
    return "".join(protein)


_cds_cache: dict[str, str | None] = {}


def _reference_protein(base: str, transcript_id: str, client: httpx.Client) -> str | None:
    if transcript_id in _cds_cache:
        return _cds_cache[transcript_id]
    cache_dir = settings.storage_path / "ensembl_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{transcript_id}.cds.txt"
    cds: str | None = None
    if cache_file.exists():
        cds = cache_file.read_text().strip()
    else:
        for attempt in range(3):
            try:
                resp = client.get(
                    f"{base}/sequence/id/{transcript_id}",
                    params={"type": "cds"},
                    headers={"Accept": "application/json"},
                    timeout=90.0,
                )
                if resp.status_code == 200:
                    payload = resp.json()
                    sequence = (
                        payload.get("seq") if isinstance(payload, dict) else None
                    )
                    if sequence:
                        cds = sequence
                        cache_file.write_text(cds)
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2 * (attempt + 1))
    protein = _translate(cds) if cds else None
    _cds_cache[transcript_id] = protein
    return protein


def _map_consequence(terms: list[str]) -> tuple[str, str]:
    for term in terms:
        for key, consequence, impact in _CONSEQUENCE_MAP:
            if term == key:
                return consequence, impact
    return Consequence.UNKNOWN.value, Impact.MODIFIER.value


def _build_peptide(protein: str | None, position: int | None, ref: str, alt: str) -> str | None:
    if not protein or not position or position < 1 or position > len(protein):
        return None
    if alt not in _STANDARD_AA:
        return None
    # Return a mutant context up to 11 aa (mutation centred), from which the
    # prediction provider enumerates 8-11mer epitope windows.
    center = position - 1
    start = max(0, center - 5)
    end = min(len(protein), center + 6)
    window = list(protein[start:end])
    window[center - start] = alt
    peptide = "".join(window)
    if len(peptide) < 8 or any(ch not in _STANDARD_AA for ch in peptide):
        return None
    return peptide


@register
class VepAnnotator(VariantAnnotator):
    name = "vep"

    def metadata(self) -> ProviderMetadata:
        base = _base(self.reference_build)
        return ProviderMetadata(
            provider=self.name,
            provider_version="REST",
            reference_build=self.reference_build or GRCH38,
            annotation_version=_ensembl_release(base),
            transcript_source="Ensembl",
            description="Ensembl VEP via the official REST API (real annotation).",
        )

    def is_available(self) -> bool:
        return _is_available(self.reference_build)

    def annotate(
        self, variants: list[VariantInput], reference_context: ReferenceContext
    ) -> list[AnnotationRecord]:
        build = reference_context.reference_build or self.reference_build or GRCH38
        base = _base(build)

        usable = [v for v in variants if v.chromosome and v.position and v.reference and v.alternate]
        records: list[AnnotationRecord] = []
        uncached: list[VariantInput] = []
        with httpx.Client(timeout=_TIMEOUT) as client:
            for variant in usable:
                entry = _read_cache(build, variant)
                if entry is not None:
                    records.append(self._record_from_entry(client, base, variant, entry))
                    continue
                uncached.append(variant)

            if uncached:
                if not _is_available(build):
                    raise ProviderUnavailableError(
                        "Ensembl VEP REST is not reachable and not all variants are "
                        "cached."
                    )
                by_input: dict[str, VariantInput] = {}
                queries: list[str] = []
                for variant in uncached:
                    chrom = (variant.chromosome or "").replace("chr", "")
                    query = (
                        f"{chrom} {variant.position} . {variant.reference} "
                        f"{variant.alternate} . . ."
                    )
                    by_input[query] = variant
                    queries.append(query)
                for start in range(0, len(queries), 150):
                    chunk = queries[start : start + 150]
                    response = _post_vep(client, base, chunk)
                    for entry in response.json():
                        variant = by_input.get(entry.get("input", ""))
                        if variant is None:
                            continue
                        _write_cache(build, variant, entry)
                        records.append(
                            self._record_from_entry(client, base, variant, entry)
                        )

        # Any usable variant without a VEP response -> explicit unknown annotation.
        answered = {r.key for r in records}
        for variant in usable:
            if variant.key not in answered:
                records.append(
                    AnnotationRecord(
                        key=variant.key,
                        status=AnnotationStatus.ANNOTATED.value,
                        consequence=Consequence.UNKNOWN.value,
                        impact=Impact.MODIFIER.value,
                    )
                )
        return records

    def _record_from_entry(
        self, client: httpx.Client, base: str, variant: VariantInput, entry: dict
    ) -> AnnotationRecord:
        consequences = entry.get("transcript_consequences") or []
        selected = _select_transcript(consequences)
        if selected is None:
            return AnnotationRecord(
                key=variant.key,
                status=AnnotationStatus.ANNOTATED.value,
                consequence=Consequence.UNKNOWN.value,
                impact=Impact.MODIFIER.value,
            )

        terms = selected.get("consequence_terms", [])
        consequence, impact = _map_consequence(terms)
        amino_acids = selected.get("amino_acids")
        position = selected.get("protein_start")
        protein_change = None
        alt_aa = None
        ref_aa = None
        if amino_acids and position:
            parts = amino_acids.split("/")
            if len(parts) == 2:
                ref_aa, alt_aa = parts[0], parts[1]
                if alt_aa == "*":
                    protein_change = f"p.{ref_aa}{position}*"
                elif ref_aa == "*":
                    protein_change = f"p.*{position}{alt_aa}"
                else:
                    protein_change = f"p.{ref_aa}{position}{alt_aa}"

        mutated_peptide = None
        if (
            consequence
            in (
                Consequence.MISSENSE.value,
                Consequence.SYNONYMOUS.value,
                Consequence.STOP_LOST.value,
            )
            and ref_aa
            and alt_aa
            and alt_aa != "*"
            and selected.get("transcript_id")
        ):
            protein = _reference_protein(base, selected["transcript_id"], client)
            mutated_peptide = _build_peptide(protein, position, ref_aa, alt_aa)

        known_variants: list[str] = []
        clinical_significance = None
        for coloc in entry.get("colocated_variants") or []:
            identifier = coloc.get("id")
            if identifier:
                known_variants.append(identifier)
            clinical_significance = (
                coloc.get("clin_sig")
                or coloc.get("clinvar_somatic_classification")
                or clinical_significance
            )

        return AnnotationRecord(
            key=variant.key,
            status=AnnotationStatus.ANNOTATED.value,
            consequence=consequence,
            impact=impact,
            gene=selected.get("gene_symbol"),
            gene_id=selected.get("gene_id"),
            transcript=selected.get("transcript_id"),
            transcript_id=selected.get("transcript_id"),
            protein_change=protein_change,
            cds_position=selected.get("cds_start"),
            protein_position=position,
            mutated_peptide=mutated_peptide,
            extra={
                "known_variants": known_variants[:25],
                "clinical_significance": clinical_significance,
                "hgvs_c": selected.get("hgvsc"),
                "hgvs_p": selected.get("hgvsp"),
            },
        )


def _select_transcript(consequences: list[dict]) -> dict | None:
    if not consequences:
        return None
    coding = [c for c in consequences if c.get("biotype") == "protein_coding"]
    pool = coding or consequences
    mane = [c for c in pool if c.get("mane_select")]
    if mane:
        pool = mane
    canonical = [c for c in pool if c.get("canonical")]
    if canonical:
        pool = canonical

    def score(entry: dict) -> int:
        consequence, _ = _map_consequence(entry.get("consequence_terms", []))
        return _SEVERITY.get(consequence, 0)
    return max(pool, key=score)
