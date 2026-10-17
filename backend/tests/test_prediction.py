import pytest

from app.prediction import (
    PredictionInput,
    get_prediction_provider,
    list_prediction_providers,
)
from app.prediction.base import ProviderStatus, ProviderUnavailableError
from app.prediction.mock import MockPredictionProvider


def _input(candidate_id="c1", peptide="MEGFPX", hla="HLA-A*02:01"):
    return PredictionInput(
        candidate_id=candidate_id,
        peptide=peptide,
        peptide_representation=f"GENE|p.K2E|{peptide}",
        hla_allele=hla,
    )


def test_mock_provider_is_explicitly_mock():
    provider = MockPredictionProvider()
    assert provider.is_mock is True
    assert provider.health_check() == ProviderStatus.MOCK
    assert provider.supported_hla() == ["*"]
    assert provider.validate_input([_input()]).ok is True


def test_mock_prediction_is_deterministic():
    provider = MockPredictionProvider()
    first = provider.predict([_input()])[0]
    second = provider.predict([_input()])[0]
    assert first.prediction_value == second.prediction_value
    assert 0.0 <= first.prediction_value <= 1.0
    assert first.metric_name == "mock_binding_score"
    assert first.status == "MOCK"
    assert first.input_hash


def test_validate_input_rejects_missing_peptide():
    provider = MockPredictionProvider()
    result = provider.validate_input([_input(peptide=None)])
    assert result.ok is False


def test_providers_list_marks_mock_and_reserved():
    providers = {p["name"]: p for p in list_prediction_providers()}
    assert providers["mock"]["is_mock"] is True
    assert providers["mock"]["status"] == "MOCK"
    assert providers["external"]["is_mock"] is False
    assert providers["external"]["status"] == "UNAVAILABLE"
    # Real MHCflurry Class I provider (never mock).
    assert providers["mhcflurry"]["is_mock"] is False
    assert providers["mhcflurry"]["provider_version"] != "unconfigured"
    # Class II (MHCnuggets, isolated runtime) and the combined panel.
    assert providers["mhcnuggets"]["is_mock"] is False
    assert providers["panel"]["is_mock"] is False


def test_reserved_external_provider_refuses_to_substitute_mock():
    provider = get_prediction_provider("external")
    assert provider.health_check() == ProviderStatus.UNAVAILABLE
    with pytest.raises(ProviderUnavailableError):
        provider.predict([_input()])
