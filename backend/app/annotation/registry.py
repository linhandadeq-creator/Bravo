"""Provider registry.

Providers register themselves by name. External providers (VEP, SnpEff,
ANNOVAR) are registered as unavailable placeholders until their runtimes are
wired up.
"""
from __future__ import annotations

import importlib

from app.annotation.base import (
    ProviderMetadata,
    UnknownProviderError,
    VariantAnnotator,
)

_REGISTRY: dict[str, type[VariantAnnotator]] = {}
_LOADED = False

_BUILTIN_MODULES = (
    "app.annotation.mock",
    "app.annotation.vep",
    "app.annotation.offline",
    "app.annotation.snpeff",
    "app.annotation.annovar",
)


def register(cls: type[VariantAnnotator]) -> type[VariantAnnotator]:
    if not getattr(cls, "name", None):
        raise ValueError("Annotator providers must define a name")
    _REGISTRY[cls.name] = cls
    return cls


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    for module in _BUILTIN_MODULES:
        importlib.import_module(module)
    _LOADED = True


def available_provider_names() -> list[str]:
    _ensure_loaded()
    return list(_REGISTRY.keys())


def get_annotator(
    name: str, reference_build: str | None = None
) -> VariantAnnotator:
    _ensure_loaded()
    cls = _REGISTRY.get(name)
    if cls is None:
        raise UnknownProviderError(
            f"Unknown annotation provider '{name}'. "
            f"Available: {', '.join(_REGISTRY) or 'none'}."
        )
    return cls(reference_build=reference_build)


def list_providers() -> list[dict]:
    _ensure_loaded()
    providers: list[dict] = []
    for name, cls in _REGISTRY.items():
        try:
            instance = cls()
            metadata: ProviderMetadata = instance.metadata()
            available = instance.is_available()
        except Exception as exc:  # noqa: BLE001 - metadata should not crash the listing
            metadata = ProviderMetadata(
                provider=name,
                provider_version="unknown",
                reference_build="unknown",
                annotation_version="unknown",
                transcript_source="unknown",
            )
            available = False
            metadata.description = str(exc)
        providers.append(
            {
                "name": name,
                "provider": metadata.provider,
                "provider_version": metadata.provider_version,
                "reference_build": metadata.reference_build,
                "annotation_version": metadata.annotation_version,
                "transcript_source": metadata.transcript_source,
                "description": metadata.description,
                "available": available,
            }
        )
    return providers
