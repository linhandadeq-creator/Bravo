from app.prediction.base import PredictionOutput, ProviderStatus
from app.prediction.consensus import aggregate, percentile_rank
from app.prediction.registry import get_prediction_provider, list_prediction_providers
from app.services.somatic_calling import status as somatic_status


def _out(provider: str, cid: str, value: float, hla: str = "HLA-A*02:01") -> PredictionOutput:
    return PredictionOutput(
        candidate_id=cid,
        hla=hla,
        prediction_value=value,
        metric_name="x",
        status="AVAILABLE",
        provider=provider,
        provider_version="1",
        input_hash="h",
    )


def test_percentile_direction():
    assert percentile_rank([1.0, 2.0, 3.0], 3.0, True) == 1.0
    assert percentile_rank([1.0, 2.0, 3.0], 1.0, True) == 0.0
    # Rank-style (lower is better) inverts.
    assert percentile_rank([1.0, 2.0, 3.0], 3.0, False) == 0.0
    assert percentile_rank([1.0, 2.0, 3.0], 1.0, False) == 1.0


def test_aggregate_combines_two_providers():
    outputs = [
        _out("mhcflurry", "c1", 0.9),
        _out("mhcflurry", "c2", 0.1),
        _out("netmhcpan", "c1", 0.5),
        _out("netmhcpan", "c2", 2.0),
    ]
    result = {r.candidate_id: r for r in aggregate(outputs)}
    assert result["c1"].detail["n_providers"] == 2
    assert result["c1"].prediction_value == 100.0
    assert result["c2"].prediction_value == 0.0
    assert result["c1"].detail["agreement"] == 1.0
    assert set(result["c1"].detail["providers"]) == {"mhcflurry", "netmhcpan"}


def test_consensus_and_adapters_registered():
    names = {p["name"] for p in list_prediction_providers()}
    assert {"consensus", "netmhcpan", "netmhciipan", "panel"} <= names


def test_adapters_unavailable_without_binary():
    assert (
        get_prediction_provider("netmhcpan").health_check()
        == ProviderStatus.UNAVAILABLE
    )
    assert (
        get_prediction_provider("netmhciipan").health_check()
        == ProviderStatus.UNAVAILABLE
    )


def test_somatic_calling_status_shape():
    report = somatic_status()
    assert "components" in report
    assert report["available"] in (True, False)
    assert set(report["components"]) >= {"bwa", "gatk_mutect2", "reference_genome"}
