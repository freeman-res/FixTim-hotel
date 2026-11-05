from backend.app.agent.intent_router import IntentRouter
from backend.app.agent.schemas import TripPatch
from backend.app.agent.query_parser import QueryParser


def test_transport_request_overrides_model_hotel_intent():
    state = {"trip": {"city": "Санкт-Петербург"}, "changed_fields": []}
    assert IntentRouter.detect("найди дорогу на 30 октября", TripPatch(intent="hotel_search"), state) == "trip_search"


def test_origin_city_answer_continues_transport_search():
    state = {"trip": {"city": "Санкт-Петербург", "origin_city": "Москва"},
             "last_intent": "trip_search", "changed_fields": ["origin_city"]}
    assert IntentRouter.detect("из Москвы", TripPatch(intent="hotel_search", origin_city="Москва"), state) == "trip_search"


def test_origin_answer_does_not_replace_destination_or_start_new_trip():
    patch = QueryParser._parse_json(
        '{"city":"Москва","origin_city":"Питер","new_trip":true,"intent":"hotel_search"}',
        "из Москвы", {"trip": {"city": "Питер"}},
    )
    assert patch.city is None
    assert patch.origin_city == "Москва"
    assert patch.new_trip is False


def test_transport_request_cannot_clear_destination():
    patch = QueryParser._parse_json(
        '{"clear_fields":["city"],"intent":"trip_search"}',
        "как мне добраться туда 20 ноября 2026", {"trip": {"city": "Питер"}},
    )
    assert "city" not in patch.clear_fields


def test_explicit_russian_date_overrides_flexible_month():
    patch = QueryParser._parse_json(
        '{"flexible_dates":"в октябре","intent":"trip_search"}',
        "найди дорогу на 30 октября 2026", {"trip": {"city": "Питер"}},
    )
    assert patch.check_in == "2026-10-30"
    assert patch.flexible_dates is None


def test_transport_date_keeps_saved_destination():
    patch = QueryParser._parse_json(
        '{"city":"","intent":"trip_search"}',
        "на завтра 30 октября найди дорогу", {"trip": {"city": "Арзамас"}},
    )
    assert patch.city is None
    assert patch.check_in == "2026-10-30"


def test_short_transport_followups_stay_in_search():
    state = {"trip": {"city": "Арзамас", "origin_city": "Москва"},
             "last_intent": "trip_search"}
    assert IntentRouter.detect("предпочтений нет", TripPatch(intent="chat"), state) == "trip_search"
    assert IntentRouter.detect("помоги найти маршрут", TripPatch(intent="chat"), state) == "trip_search"


def test_tomorrow_sets_exact_date():
    from datetime import date, timedelta
    patch = QueryParser._parse_json('{"intent":"chat"}', "найди дорогу на завтра", {})
    assert patch.check_in == (date.today() + timedelta(days=1)).isoformat()


def test_tomorrow_keeps_trip_length():
    from backend.app.agent.state_manager import StateManager
    state = {"trip": {"city": "Арзамас", "origin_city": "Москва",
                      "check_in": "2026-11-10", "check_out": "2026-11-15"}}
    patch = TripPatch(check_in="2026-10-30")
    updated = StateManager.update(state, patch)
    assert updated["trip"]["check_out"] == "2026-11-04"
    assert updated["trip"]["nights"] == 5
