"""Состояние всей поездки: точечные изменения и инвалидирование зависимостей."""
from copy import deepcopy
from datetime import date, timedelta
from .schemas import TripPatch

TRIP_FIELDS = (
    "city", "destination_id", "origin_city", "check_in", "check_out", "return_date",
    "nights", "travel_month", "travel_year", "flexible_dates", "guests",
    "adults", "children", "pets", "max_total_price", "max_total_budget",
    "currency", "transport_mode", "max_travel_hours", "required_amenities", "preferences",
)
PATCH_CONTROL_FIELDS = {
    "new_trip", "intent", "clear_fields", "shift_days",
    "reject_hotel_ids", "reject_result_numbers", "remove_required_amenities",
    "remove_preferences",
}


class StateManager:
    @staticmethod
    def update(state: dict, patch: TripPatch) -> dict:
        result = {} if patch.new_trip else deepcopy(state or {})
        trip = dict(result.get("trip", {}))
        previous = deepcopy(trip)

        prior_hotel_ids = list(result.get("last_hotel_ids", []))

        explicit = patch.model_dump(exclude_unset=True, exclude=PATCH_CONTROL_FIELDS)
        changed_keys = set()
        for key in patch.clear_fields:
            if key in trip:
                trip.pop(key)
                changed_keys.add(key)

        for key, value in explicit.items():
            if key not in TRIP_FIELDS or value is None:
                continue
            if key in ("required_amenities", "preferences"):
                original = list(trip.get(key) or [])
                existing_lower = {s.casefold() for s in original}
                for item in value:
                    item = str(item).strip()
                    if item and item.casefold() not in existing_lower:
                        original.append(item)
                        existing_lower.add(item.casefold())
                trip[key] = original
            else:
                trip[key] = value

        for key, values in (("required_amenities", patch.remove_required_amenities),
                            ("preferences", patch.remove_preferences)):
            if values:
                remove = {str(s).casefold() for s in values}
                trip[key] = [v for v in (trip.get(key) or []) if v.casefold() not in remove]


        if ({"travel_month", "travel_year", "flexible_dates"} & explicit.keys()) and not (
            {"check_in", "check_out"} & explicit.keys()
        ):
            trip.pop("check_in", None)
            trip.pop("check_out", None)


        if "nights" in explicit and "check_out" not in explicit and trip.get("check_in"):
            trip["check_out"] = (
                date.fromisoformat(trip["check_in"]) + timedelta(days=int(trip["nights"]))
            ).isoformat()
        elif "check_in" in explicit and "check_out" not in explicit and previous.get("check_in") and previous.get("check_out"):
            duration = (date.fromisoformat(previous["check_out"]) - date.fromisoformat(previous["check_in"])).days
            trip["check_out"] = (date.fromisoformat(trip["check_in"]) + timedelta(days=duration)).isoformat()


        if patch.shift_days is not None and patch.shift_days != 0:
            if not trip.get("check_in") and not trip.get("check_out"):
                result.setdefault("warnings", []).append("Не были указаны точные даты для сдвига")
            else:
                for key in ("check_in", "check_out", "return_date"):
                    if trip.get(key) and key not in explicit:
                        trip[key] = (date.fromisoformat(trip[key]) + timedelta(days=patch.shift_days)).isoformat()


        if ("check_in" in explicit or "check_out" in explicit) and (
            "travel_month" not in explicit and "travel_year" not in explicit and "flexible_dates" not in explicit
        ):
            for field in ("travel_month", "travel_year", "flexible_dates"):
                trip.pop(field, None)

        if trip.get("check_in") and trip.get("check_out"):
            start = date.fromisoformat(trip["check_in"])
            end = date.fromisoformat(trip["check_out"])
            if end <= start:
                raise ValueError("Дата выезда должна быть позже даты заезда")
            trip["nights"] = (end - start).days
        elif {"check_in", "check_out"}.intersection(changed_keys | explicit.keys()):


            if "nights" not in explicit:
                trip.pop("nights", None)


        if ("adults" in explicit or "children" in explicit) and "guests" not in explicit:
            if trip.get("adults") is not None:
                trip["guests"] = int(trip["adults"]) + int(trip.get("children") or 0)

        changed_keys.update(key for key in set(previous) | set(trip) if previous.get(key) != trip.get(key))
        if "check_out" in changed_keys and "return_date" not in explicit and patch.shift_days is None:
            if trip.pop("return_date", None) is not None:
                changed_keys.add("return_date")
        result["trip"] = trip
        result["changed_fields"] = sorted(changed_keys)


        selection_changes = {"city", "destination_id", "origin_city", "check_in", "check_out", "return_date", "nights", "guests", "adults", "children", "pets", "transport_mode", "travel_month", "travel_year", "flexible_dates"}
        preference_changes = {"max_total_budget", "max_total_price", "required_amenities", "preferences", "max_travel_hours", "currency"}
        if changed_keys & (selection_changes | preference_changes):
            if result.get("itinerary") is not None or result.get("cart") is not None:
                result["needs_replan"] = True
                result["itinerary"] = None
                result["cart"] = None
                result["demo_booking"] = None
            result.pop("demo_booked", None)
            result.pop("booking_status", None)
            result.pop("demo_booking_id", None)
            result["last_hotel_ids"] = []
            result["last_hotel_offers"] = []
            if changed_keys & selection_changes:
                result["selected_return_transport"] = None
                result["last_return_options"] = []
                result["transfer_routes"] = {}
                if changed_keys & {"city", "destination_id", "origin_city", "check_in", "check_out",
                                   "travel_month", "travel_year", "flexible_dates", "adults",
                                   "children", "guests", "transport_mode"}:
                    result["selected_transport"] = None
                    result["last_transport_options"] = []
                    result["last_transport_ids"] = []
                if changed_keys & {"city", "destination_id", "check_in", "check_out",
                                   "travel_month", "travel_year", "flexible_dates", "adults",
                                   "children", "guests", "pets"}:
                    result["selected_hotel"] = None
                selection = dict(result.get("selected") or {})
                if "return_date" in changed_keys:
                    selection["return_transport_id"] = None
                if changed_keys & {"city", "destination_id", "check_in", "check_out", "travel_month", "travel_year", "flexible_dates", "guests", "adults", "children", "pets"}:
                    selection["hotel_offer_id"] = None
                    selection["hotel_name"] = None
                if changed_keys & {"city", "destination_id", "origin_city", "check_in", "check_out", "travel_month", "travel_year", "flexible_dates", "guests", "adults", "children", "pets", "transport_mode"}:
                    selection["outbound_transport_id"] = None
                    selection["return_transport_id"] = None
                    selection["transfer_id"] = None
                if selection:
                    result["selected"] = selection

        if changed_keys & preference_changes:
            result["selected_hotel"] = None
            selection = dict(result.get("selected") or {})
            selection["hotel_offer_id"] = None
            selection["hotel_name"] = None
            if selection:
                result["selected"] = selection

        rejected = {str(v) for v in result.get("rejected_hotel_ids", [])}
        rejected.update(str(v) for v in patch.reject_hotel_ids)
        for number in patch.reject_result_numbers:
            if 1 <= number <= len(prior_hotel_ids):
                rejected.add(str(prior_hotel_ids[number - 1]))
        result["rejected_hotel_ids"] = sorted(rejected)
        return result

    @staticmethod
    def missing_fields(state: dict, intent: str = "hotel_search") -> list[str]:
        """Поля зависят от текущего действия, не общая анкета на любую реплику."""
        if intent not in ("hotel_search", "trip_search"):
            return []
        trip = state.get("trip", {})
        missing = []
        if intent == "hotel_search":
            if not trip.get("city"):
                missing.append("город")
            return missing
        if not trip.get("origin_city"):
            missing.append("город отправления")
        if not trip.get("city"):
            missing.append("город назначения")
        return missing

    @staticmethod
    def add_history(state: dict, user_message: str, assistant_message: str) -> dict:
        state = deepcopy(state)
        history = list(state.get("history", []))
        history.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ])
        state["history"] = history[-16:]
        return state
