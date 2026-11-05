from __future__ import annotations

from backend.app.catalog.hotels.service import HotelsService
from backend.app.catalog.transport.service import TransportService
from backend.app.catalog.providers.json import JsonProvider
from backend.app.agent.ranking.scorer import rank_offers


class FakeTutu:
    def __init__(self, flights=None, hotels=None, trains=None, error=False):
        self.flights = flights or {"offers": []}
        self.hotels = hotels or {"hotels": []}
        self.trains = trains or {"offers": []}
        self.error = error
        self.calls = []

    def search_avia(self, **kwargs):
        self.calls.append(("avia", kwargs))
        if self.error:
            raise TimeoutError("offline")
        return self.flights

    def search_hotels(self, **kwargs):
        self.calls.append(("hotels", kwargs))
        if self.error:
            raise TimeoutError("offline")
        return self.hotels

    def search_rail(self, **kwargs):
        self.calls.append(("rail", kwargs))
        if self.error:
            raise TimeoutError("offline")
        return self.trains


def test_live_flight_precedes_estimate(test_data_dir):
    live = FakeTutu(flights={"offers": [{
        "offer_id": "abc", "price": {"amount": 2758, "currency": "RUB"},
        "departure_at": "2026-11-18T19:40:00+03:00",
        "arrival_at": "2026-11-18T21:35:00+03:00",
        "duration_min": 115, "segments_count": 1,
        "search_results_url": "https://avia.tutu.ru/f/Moskva/Kazan/",
        "legs": [{"segments": [{"voyage_no": "N4-59"}]}],
    }]})
    service = TransportService(JsonProvider(test_data_dir), live_client=live)
    result = service.find_transport({"type": "plane", "from_city": "Москва", "to_city": "Казань", "date_from": "2026-11-18"})
    assert len(result) == 1
    assert result[0]["price"]["amount_min_rub"] == 2758
    assert result[0]["price_estimate"] is None
    assert result[0]["source"]["name"] == "Tutu MCP"
    assert result[0]["departure_utc"].startswith("2026-11-18")
    assert live.calls[0][0] == "avia"


def test_empty_or_invalid_flight_uses_route_estimate(test_data_dir):
    for offer in (None, {"offer_id": "bad", "price": {"amount": 0, "currency": "RUB"}}):
        live = FakeTutu(flights={"offers": [offer] if offer else []})
        service = TransportService(JsonProvider(test_data_dir), live_client=live)
        result = service.find_transport({"type": "plane", "from_city": "Москва", "to_city": "Казань", "date_from": "2026-11-18"})
        assert len(result) == 1
        assert result[0]["record_kind"] == "route_price_estimate"
        assert result[0]["price"] is None
        assert result[0]["price_estimate"]["currency"] == "RUB"
        assert result[0]["price_estimate"]["amount_rub"] > 0
        assert result[0]["booking_url"] is None
        assert result[0]["departure_utc"] is None


def test_flight_api_failure_uses_estimate(test_data_dir):
    service = TransportService(JsonProvider(test_data_dir), live_client=FakeTutu(error=True))
    result = service.find_transport({"type": "plane", "from_city": "Москва", "to_city": "Сочи", "date_from": "2026-11-15"})
    assert result[0]["record_kind"] == "route_price_estimate"


def test_live_hotel_precedes_synthetic_prices(test_data_dir):
    live = FakeTutu(hotels={"hotels": [{
        "hotel_id": "11844608", "name": "Отель Булгар", "stars": 2,
        "rating": 8.28, "location": {"lat": 55.78, "lng": 49.15},
        "checkout_url": "https://hotel.tutu.ru/offers/details",
        "best_offer": {"price": {"amount": 15719, "currency": "RUB"}, "price_basis": "stay_total"},
    }], "stay": {"check_in": "2026-11-18", "check_out": "2026-11-20", "nights": 2}})
    service = HotelsService(JsonProvider(test_data_dir), live_client=live)
    result = service.find_offers({"city": "Казань", "check_in": "2026-11-18", "check_out": "2026-11-20", "guests": 2})
    assert len(result) == 1
    assert result[0]["hotel_id"] == "tutu_11844608"
    assert result[0]["total_price"] == 15719
    assert result[0]["price_estimate"] is None
    assert result[0]["source"]["name"] == "Tutu MCP"
    assert service.get_hotel("tutu_11844608") == result[0]


def test_hotel_api_failure_uses_synthetic_price_without_claiming_availability(test_data_dir):
    service = HotelsService(JsonProvider(test_data_dir), live_client=FakeTutu(error=True))
    result = service.find_offers({"city": "Санкт-Петербург", "check_in": "2026-11-18", "check_out": "2026-11-20"})
    assert len(result) == 1
    hotel = result[0]
    assert hotel["hotel_id"] == "hotel_t_003"
    assert hotel["price"] is None
    assert hotel["price_estimate"]["amount_rub"] > 0
    assert hotel["price_estimate"]["unit"] == "per_night"
    assert hotel["availability"]["status"] == "unknown"
    assert hotel.get("total_price") is None


def test_no_dates_does_not_call_live_hotel_api(test_data_dir):
    live = FakeTutu()
    service = HotelsService(JsonProvider(test_data_dir), live_client=live)
    service.find_offers({"city": "Москва"})
    assert live.calls == []


def test_live_train_precedes_rzd(test_data_dir, monkeypatch):
    live = FakeTutu(trains={"offers": [{
        "offer_id": "train1", "price": {"amount": 1343.57, "currency": "RUB"},
        "departure_at": "2026-11-18T00:20:00+03:00",
        "arrival_at": "2026-11-18T13:27:00+03:00",
        "search_results_url": "https://www.tutu.ru/poezda/rasp_d.php",
        "duration_min": 787, "segments_count": 1,
        "legs": [{"segments": [{"voyage_no": "130Х"}]}],
    }]})
    service = TransportService(JsonProvider(test_data_dir), live_client=live)
    monkeypatch.setattr("backend.app.catalog.transport.service.RzdTrainProvider",
                        lambda: (_ for _ in ()).throw(AssertionError("RZD should not be called")))
    result = service.find_transport({"type": "train", "from_city": "Москва", "to_city": "Казань", "date_from": "2026-11-18"})
    assert len(result) == 1
    assert result[0]["record_kind"] == "live_offer"
    assert result[0]["price"]["amount_min_rub"] == 1343.57
    assert result[0]["schedule_date"] == "2026-11-18"
    assert result[0]["departure_utc"].startswith("2026-11-17")


def test_estimate_is_soft_ranking_signal_not_budget_proof():
    offers = [
        {"hotel_id": "a_expensive", "city": "Казань", "total_price": None, "amenities": [],
         "price_estimate": {"amount_rub": 10000, "currency": "RUB", "unit": "per_night"}},
        {"hotel_id": "z_cheap", "city": "Казань", "total_price": None, "amenities": [],
         "price_estimate": {"amount_rub": 3000, "currency": "RUB", "unit": "per_night"}},
    ]
    ranked = rank_offers(offers, {"city": "Казань", "check_in": "2026-11-18",
                                   "check_out": "2026-11-20", "max_total_price": 10000}, [], set())
    assert [h["hotel_id"] for h in ranked] == ["z_cheap", "a_expensive"]
    assert all(h["total_price"] is None for h in ranked)
    assert all("не подтверждено" in h["reason"] for h in ranked)
    assert "примерно" in ranked[0]["reason"].lower()
