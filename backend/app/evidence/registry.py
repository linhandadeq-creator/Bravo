"""Evidence provider registry (mirrors the prediction registry)."""
from __future__ import annotations

import importlib

from app.evidence.base import EvidenceStatus, VariantEvidenceProvider

_REGISTRY: dict[str, type[VariantEvidenceProvider]] = {}
_LOADED = False

_BUILTIN_MODULES = (
    "app.evidence.mock",
    "app.evidence.gnomad",
    "app.evidence.clinvar",
    "app.evidence.cosmic",
)


class UnknownEvidenceProviderError(ValueError):
    pass


def register_evidence_provider(
    cls: type[VariantEvidenceProvider],
) -> type[VariantEvidenceProvider]:
    if not getattr(cls, "provider_name", None):
        raise ValueError("Evidence providers must define provider_name")
    _REGISTRY[cls.provider_name] = cls
    return cls


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    for module in _BUILTIN_MODULES:
        importlib.import_module(module)
    _LOADED = True


def get_evidence_provider(name: str) -> VariantEvidenceProvider:
    _ensure_loaded()
    cls = _REGISTRY.get(name)
    if cls is None:
        raise UnknownEvidenceProviderError(
            f"Unknown evidence provider '{name}'. "
            f"Available: {', '.join(_REGISTRY) or 'none'}."
        )
    return cls()


def list_evidence_providers() -> list[dict]:
    _ensure_loaded()
    providers: list[dict] = []
    for name, cls in _REGISTRY.items():
        instance = cls()
        status = instance.health_check()
        providers.append(
            {
                "name": name,
                "provider_name": instance.provider_name,
                "provider_version": instance.provider_version,
                "is_mock": instance.is_mock,
                "supported_builds": list(instance.supported_builds),
                "status": status.value,
                "description": instance.description,
            }
        )
    return providers


def available_evidence_providers() -> list[VariantEvidenceProvider]:
    """Providers that can serve queries right now (mock included)."""
    return [
        cls()
        for name, cls in _REGISTRY.items()
        if cls().health_check() in (EvidenceStatus.MOCK, EvidenceStatus.AVAILABLE)
    ]
