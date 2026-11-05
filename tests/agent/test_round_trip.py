from backend.app.agent.trip_assembly import assemble_trip
from backend.app.services.agent_service import handle_action, assemble_with_transfers
import asyncio


def test_return_leg_and_transfer_estimates_are_itemized():
    state = {
        "trip": {"city": "Казань", "origin_city": "Москва", "check_in": "2026-11-20",
                 "check_out": "2026-11-22", "return_date": "2026-11-23", "adults": 1},
        "selected_hotel": {"hotel_id": "h1", "name": "Отель", "record_kind": "live_offer",
                           "total_price": 8000, "currency": "RUB"},
        "selected_transport": {"transport_id": "out", "type": "plane", "record_kind": "live_offer",
                               "from": {"city": "Москва"}, "to": {"city": "Казань"},
                               "price": {"amount_min_rub": 4000, "currency": "RUB", "unit": "per_person_one_way"}},
        "selected_return_transport": {"transport_id": "back", "type": "plane", "record_kind": "live_offer",
                                      "from": {"city": "Казань"}, "to": {"city": "Москва"},
                                      "price": {"amount_min_rub": 5000, "currency": "RUB", "unit": "per_person_one_way"}},
        "transfer_routes": {"arrival": {"distance_km": 28, "duration_minutes": 53, "price_estimate_rub": 1250}},
    }
    cart = assemble_trip(state)["cart"]
    assert [item["type"] for item in cart["items"]] == ["transport", "hotel", "return_transport", "transfer"]
    assert cart["total"] == 18250
    assert cart["complete"] is False
    assert cart["items"][-1]["estimated"] is True


def test_missing_return_is_unknown_and_total_is_partial():
    state = {
        "trip": {"city": "Казань", "origin_city": "Москва", "check_in": "2026-11-20",
                 "check_out": "2026-11-22", "adults": 1},
        "selected_hotel": {"hotel_id": "h1", "name": "Отель", "record_kind": "live_offer",
                           "total_price": 8000, "currency": "RUB"},
        "selected_transport": {"transport_id": "out", "type": "plane", "record_kind": "live_offer",
                               "from": {"city": "Москва"}, "to": {"city": "Казань"},
                               "price": {"amount_min_rub": 4000, "currency": "RUB", "unit": "per_person_one_way"}},
    }
    cart = assemble_trip(state)["cart"]
    assert cart["scope"] == "outbound_transport_and_hotel_only"
    assert cart["complete"] is False
    assert cart["items"][-1]["type"] == "return_transport"
    assert cart["items"][-1]["price"] is None


def test_return_search_uses_checkout_date_and_reverse_route():
    class Catalog:
        async def find_transport(self, filters):
            assert filters["from_city"] == "Казань"
            assert filters["to_city"] == "Москва"
            assert filters["date_from"] == "2026-11-22"
            return [{"transport_id": "back", "type": "plane", "record_kind": "live_offer",
                     "from": {"city": "Казань"}, "to": {"city": "Москва"},
                     "price": {"amount_min_rub": 5000, "currency": "RUB", "unit": "per_person_one_way"}}]

    state = {
        "trip": {"city": "Казань", "origin_city": "Москва", "check_in": "2026-11-20",
                 "check_out": "2026-11-22", "adults": 1},
        "selected_hotel": {"hotel_id": "h1", "name": "Отель", "total_price": 8000,
                           "currency": "RUB", "record_kind": "live_offer"},
        "selected_transport": {"transport_id": "out", "type": "plane", "record_kind": "live_offer",
                               "from": {"city": "Москва"}, "to": {"city": "Казань"},
                               "price": {"amount_min_rub": 4000, "currency": "RUB", "unit": "per_person_one_way"}},
    }
    found = asyncio.run(handle_action("search_return_transport", "2026-11-22", state,
                                      "Обратно", catalog=Catalog()))
    assert found.transport_options[0]["trip_leg"] == "return"
    assert found.updated_state["trip"]["return_date"] == "2026-11-22"
    selected = asyncio.run(handle_action("select_return_transport", "back",
                                         found.updated_state, "Выбираю", catalog=Catalog()))
    assert selected.updated_state["cart"]["total"] == 17000
    assert selected.updated_state["selected"]["return_transport_id"] == "back"


def test_selected_flight_uses_osrm_route_to_hotel(monkeypatch):
    class Router:
        def route(self, start, end):
            assert start == (55.6062, 49.2787)
            assert end == (55.79, 49.12)
            return {"distance_km": 28, "duration_minutes": 53, "price_estimate_rub": 1300}

    monkeypatch.setattr("backend.app.services.agent_service.get_transfer_router", lambda: Router())
    state = {
        "trip": {"city": "Казань", "origin_city": "Москва", "check_in": "2026-11-20",
                 "check_out": "2026-11-22", "adults": 1},
        "selected_hotel": {"hotel_id": "h1", "name": "Отель", "record_kind": "live_offer",
                           "total_price": 8000, "currency": "RUB",
                           "location": {"latitude": 55.79, "longitude": 49.12}},
        "selected_transport": {"transport_id": "out", "type": "plane", "record_kind": "live_offer",
                               "from": {"city": "Москва"}, "to": {"city": "Казань"},
                               "price": {"amount_min_rub": 4000, "currency": "RUB", "unit": "per_person_one_way"}},
    }
    result = asyncio.run(assemble_with_transfers(state))
    assert result["transfer_routes"]["arrival"]["distance_km"] == 28
    assert result["cart"]["total"] == 13300
