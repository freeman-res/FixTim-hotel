from backend.app.agent.query_parser import QueryParser
from backend.app.agent.schemas import TripPatch
from backend.app.agent.state_manager import StateManager


def test_null_fields_from_model_do_not_block_relative_date_shift():
    state = {"trip": {"city": "Казань", "check_in": "2026-11-20",
                      "check_out": "2026-11-22", "nights": 2}}
    raw = TripPatch(shift_days=2, intent="hotel_search").model_dump_json()
    patch = QueryParser._parse_json(raw, "На два дня позже", state)
    updated = StateManager.update(state, patch)
    assert updated["trip"]["check_in"] == "2026-11-22"
    assert updated["trip"]["check_out"] == "2026-11-24"
