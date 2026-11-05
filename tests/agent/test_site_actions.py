import asyncio

from backend.app.services.agent_service import handle_action


class Catalog:
    async def get_destination(self, destination_id):
        if destination_id == "dest_kazan":
            return {"destination_id": destination_id, "name": "Казань"}
        return None

    async def find_offers(self, filters):
        assert filters["city"] == "Казань"
        return [{"hotel_id": "h1", "name": "Отель Казань", "city": "Казань",
                 "location": {"city": "Казань"}, "stars": 4,
                 "total_price": 12000, "currency": "RUB",
                 "price": {"total_amount": 12000, "unit": "per_stay", "currency": "RUB"}}]

    async def get_hotel(self, hotel_id):
        if hotel_id == "h1":
            return {"hotel_id": "h1", "name": "Отель Казань", "city": "Казань",
                    "location": {"city": "Казань"}, "stars": 4,
                    "total_price": 12000, "currency": "RUB"}
        return None


def run(awaitable):
    return asyncio.run(awaitable)


def test_destination_click_searches_real_catalog_without_llm():
    result = run(handle_action("select_destination", "dest_kazan",
                               {"trip": {"origin_city": "Москва"}},
                               "Выбираю Казань", catalog=Catalog()))
    assert result.status == "results"
    assert result.updated_state["trip"]["city"] == "Казань"
    assert result.updated_state["trip"]["origin_city"] == "Москва"
    assert result.updated_state["last_hotel_ids"] == ["h1"]
    assert result.hotels[0]["hotel_id"] == "h1"


def test_hotel_click_only_accepts_current_search_result():
    state = {"trip": {"city": "Казань"}, "last_hotel_ids": ["h1"]}
    selected = run(handle_action("select_hotel", "h1", state,
                                 "Выбираю отель", catalog=Catalog()))
    assert selected.status == "results"
    assert selected.updated_state["selected"]["hotel_offer_id"] == "h1"
    assert selected.hotels[0]["name"] == "Отель Казань"
    rejected = run(handle_action("select_hotel", "h2", state,
                                 "Выбираю чужой отель", catalog=Catalog()))
    assert rejected.status == "clarification"
    assert rejected.updated_state.get("selected") is None


def test_hotel_click_keeps_live_offer_from_session_when_catalog_cache_is_empty():
    live = {"hotel_id": "live-1", "name": "Тариф на даты", "city": "Казань",
            "location": {"city": "Казань"}, "record_kind": "live_offer",
            "total_price": 12345, "currency": "RUB",
            "price": {"total_amount": 12345, "unit": "per_stay", "currency": "RUB"}}
    state = {"trip": {"city": "Казань", "check_in": "2026-11-20",
                      "check_out": "2026-11-22"},
             "last_hotel_ids": ["live-1"], "last_hotel_offers": [live]}
    result = run(handle_action("select_hotel", "live-1", state,
                               "Выбираю тариф", catalog=Catalog()))
    assert result.updated_state["selected_hotel"]["total_price"] == 12345
    assert result.updated_state["selected_hotel"]["record_kind"] == "live_offer"


def test_changed_hotel_budget_invalidates_previous_result():
    from backend.app.agent.schemas import TripPatch
    from backend.app.agent.state_manager import StateManager

    state = {"trip": {"city": "Казань", "max_total_price": 20000},
             "last_hotel_ids": ["h1"],
             "last_hotel_offers": [{"hotel_id": "h1", "total_price": 12000}],
             "selected": {"hotel_offer_id": "h1", "hotel_name": "Отель Казань"},
             "selected_hotel": {"hotel_id": "h1", "total_price": 12000},
             "demo_booked": True, "booking_status": "confirmed",
             "demo_booking_id": "DEMO-OLD"}
    changed = StateManager.update(state, TripPatch(max_total_price=5000))
    assert changed["last_hotel_ids"] == []
    assert changed["last_hotel_offers"] == []
    assert changed["selected_hotel"] is None
    assert changed["selected"]["hotel_offer_id"] is None
    assert changed.get("demo_booked") is None
    assert changed.get("demo_booking_id") is None


def test_transport_click_assembles_partial_route_and_demo_cart():
    state = {
        "trip": {"city": "Казань", "check_in": "2026-11-20",
                 "check_out": "2026-11-22", "adults": 1},
        "selected_hotel": {"hotel_id": "h1", "name": "Отель Казань",
                           "price_estimate": {"amount_rub": 4500, "unit": "per_night"}},
        "last_transport_options": [{"transport_id": "t1", "type": "plane",
            "record_kind": "route_price_estimate", "from": {"city": "Москва"},
            "to": {"city": "Казань"}, "schedule_date": "2026-11-20",
            "price_estimate": {"amount_rub": 6000, "unit": "per_person_one_way"}}],
    }
    result = run(handle_action("select_transport", "t1", state,
                               "Выбираю дорогу", catalog=Catalog()))
    assert result.status == "results"
    assert result.updated_state["selected"]["outbound_transport_id"] == "t1"
    assert result.cart["total"] == 15000
    assert result.cart["has_estimates"] is True


def test_replanning_clears_stale_selected_snapshots():
    from backend.app.agent.schemas import TripPatch
    from backend.app.agent.state_manager import StateManager
    state = {"trip": {"city": "Казань", "check_in": "2026-11-20"},
             "selected_hotel": {"hotel_id": "h1"},
             "selected_transport": {"transport_id": "t1"},
             "last_transport_options": [{"transport_id": "t1"}]}
    result = StateManager.update(state, TripPatch(city="Сочи"))
    assert result.get("selected_hotel") is None
    assert result.get("selected_transport") is None
    assert result.get("last_transport_options") == []
