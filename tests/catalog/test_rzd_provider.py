import pytest
from pathlib import Path

from backend.app.catalog.transport.rzd_provider import RzdTrainProvider
from backend.app.catalog.transport.rzd_provider import RzdPartialSearchError


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def search_tickets_detailed(self, origin, destination, departure_date, **kwargs):
        self.calls.append((origin, destination, departure_date, kwargs))
        if self.error:
            raise self.error
        return self.result


class Train:
    number = "016А"
    display_number = "016А"
    local_departure_time = "2026-11-04T20:00:00"
    local_arrival_time = "2026-11-05T08:00:00"
    origin_name = "Москва Ярославская"
    destination_name = "Казань-1"
    min_price = 4200


class Result:
    trains = [Train()]
    partial = False
    moscow_time = "2026-10-28T12:00:00+03:00"


def test_rzd_uses_project_ca_bundle_by_default(monkeypatch):
    monkeypatch.delenv("RZD_CA_BUNDLE", raising=False)
    provider = RzdTrainProvider()
    expected = Path(__file__).resolve().parents[2] / "data/certs/rzd_ca_bundle.pem"
    assert Path(provider.client.config.ca_bundle) == expected


def test_maps_rzd_train_to_shared_transport_shape():
    client = FakeClient(result=Result())
    provider = RzdTrainProvider(client=client)

    found = provider.search("Москва", "Казань", "2026-11-04")

    assert len(found) == 1
    assert found[0]["type"] == "train"
    assert found[0]["from"]["city"] == "Москва"
    assert found[0]["to"]["city"] == "Казань"
    assert found[0]["departure_time_local"].startswith("2026-11-04T20:00:00")
    assert found[0]["source"]["name"] == "РЖД"
    assert found[0]["availability"]["status"] == "unconfirmed"
    assert found[0]["duration_minutes"] == 720
    assert client.calls[0][0:3] == ("Москва", "Казань", "2026-11-04")


def test_empty_rzd_response_is_empty_list():
    result = type("EmptyResult", (), {"trains": [], "partial": False})()
    assert RzdTrainProvider(client=FakeClient(result=result)).search(
        "Москва", "Казань", "2026-11-04"
    ) == []


def test_partial_response_is_marked_on_each_option():
    result = type("PartialResult", (), {"trains": [Train()], "partial": True})()
    found = RzdTrainProvider(client=FakeClient(result=result)).search(
        "Москва", "Казань", "2026-11-04"
    )
    assert found[0]["source"]["partial"] is True


def test_partial_empty_response_is_not_treated_as_no_trains():
    result = type("PartialEmptyResult", (), {"trains": [], "partial": True})()
    provider = RzdTrainProvider(client=FakeClient(result=result))
    with pytest.raises(RzdPartialSearchError):
        provider.search("Москва", "Казань", "2026-11-04")


def test_rzd_upstream_errors_are_not_converted_to_empty_results():
    from rzd_api.exceptions import RzdTransportError

    provider = RzdTrainProvider(client=FakeClient(error=RzdTransportError("offline")))
    with pytest.raises(RzdTransportError):
        provider.search("Москва", "Казань", "2026-11-04")


@pytest.mark.asyncio
async def test_transport_service_routes_only_train_queries_to_rzd(monkeypatch, gateway):
    from backend.app.catalog.transport import service as transport_service

    calls = []

    class StubRzd:
        def search(self, origin, destination, departure_date):
            calls.append((origin, destination, departure_date))
            return [{"transport_id": "rzd:1", "type": "train", "from": {"city": origin},
                     "to": {"city": destination}, "schedule_date": departure_date, "price": None}]

    monkeypatch.setattr(transport_service, "RzdTrainProvider", lambda: StubRzd())
    found = await gateway.find_transport({
        "type": "train", "from_city": "Москва", "to_city": "Казань",
        "date_from": "2026-11-04",
    })

    assert found[0]["transport_id"] == "rzd:1"
    assert calls == [("Москва", "Казань", "2026-11-04")]


@pytest.mark.asyncio
async def test_search_transport_requires_a_concrete_train_date():
    from backend.app.agent.schemas import SearchTransportArgs
    from backend.app.agent.tools.search_transport import search_transport

    class Catalog:
        async def find_transport(self, _filters):
            raise AssertionError("catalog must not be called without a date")

    result = await search_transport(
        SearchTransportArgs(from_city="Москва", to_city="Казань", type="train"),
        Catalog(), {"trip": {}},
    )

    assert result["outcome"] == "clarification"
    assert "точная дата" in result["message"]


@pytest.mark.asyncio
async def test_search_transport_rejects_train_date_ranges():
    from backend.app.agent.schemas import SearchTransportArgs
    from backend.app.agent.tools.search_transport import search_transport

    class Catalog:
        async def find_transport(self, _filters):
            raise AssertionError("RZD accepts one departure date per search")

    result = await search_transport(
        SearchTransportArgs(from_city="Москва", to_city="Казань", type="train",
                           date_from="2026-11-04", date_to="2026-11-05"),
        Catalog(), {"trip": {}},
    )
    assert result["outcome"] == "clarification"
    assert "одну дату" in result["message"]
