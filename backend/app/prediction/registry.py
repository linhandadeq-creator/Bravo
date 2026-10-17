"""Prediction provider registry."""
from __future__ import annotations

import importlib

from app.prediction.base import PredictionProvider

_REGISTRY: dict[str, type[PredictionProvider]] = {}
_LOADED = False

_BUILTIN_MODULES = (
    "app.prediction.mock",
    "app.prediction.mhcflurry_provider",
    "app.prediction.mhcnuggets_provider",
    "app.prediction.netmhcpan_provider",
    "app.prediction.mixmhcpred_provider",
    "app.prediction.prime_provider",
    "app.prediction.netchop_provider",
    "app.prediction.panel",
    "app.prediction.consensus",
    "app.prediction.adapter",
)


class UnknownPredictionProviderError(ValueError):
    pass


def register_prediction_provider(
    cls: type[PredictionProvider],
) -> type[PredictionProvider]:
    if not getattr(cls, "provider_name", None):
        raise ValueError("Prediction providers must define provider_name")
    _REGISTRY[cls.provider_name] = cls
    return cls


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    for module in _BUILTIN_MODULES:
        importlib.import_module(module)
    _LOADED = True


def get_prediction_provider(name: str) -> PredictionProvider:
    _ensure_loaded()
    cls = _REGISTRY.get(name)
    if cls is None:
        raise UnknownPredictionProviderError(
            f"Unknown prediction provider '{name}'. "
            f"Available: {', '.join(_REGISTRY) or 'none'}."
        )
    return cls()


def list_prediction_providers() -> list[dict]:
    _ensure_loaded()
    providers: list[dict] = []
    for name, cls in _REGISTRY.items():
        instance = cls()
        providers.append(
            {
                "name": name,
                "provider_name": instance.provider_name,
                "provider_version": instance.provider_version,
                "is_mock": instance.is_mock,
                "supported_hla": instance.supported_hla(),
                "status": instance.health_check().value,
                "description": instance.description,
            }
        )
    return providers
