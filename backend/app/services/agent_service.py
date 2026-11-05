
from functools import lru_cache
import asyncio
from datetime import date
from copy import deepcopy
from typing import Any

from backend.app.agent import AgentOrchestrator
from backend.app.agent.schemas import AgentResponse
from backend.app.agent.schemas import SearchFilters, SearchHotelsArgs, TripPatch
from backend.app.agent.response_builder import make_response
from backend.app.agent.state_manager import StateManager
from backend.app.agent.tools.search_hotels import search_hotels
from backend.app.agent.trip_assembly import assemble_trip
from backend.app.agent.tools.catalog_adapter import AgentCatalogAdapter
from backend.app.catalog.service import get_catalog_gateway
from backend.app.catalog.transfers.osrm import OsrmTransferRouter, arrival_point


@lru_cache(maxsize=1)
def get_transfer_router() -> OsrmTransferRouter:
    return OsrmTransferRouter()


def clear_demo_booking(state: dict) -> None:
    for key in ("demo_booking", "demo_booked", "booking_status", "demo_booking_id"):
        state.pop(key, None)


async def assemble_with_transfers(state: dict) -> dict:
    hotel = state.get("selected_hotel") or {}
    location = hotel.get("location") or {}
    lat, lon = location.get("latitude"), location.get("longitude")
    routes = {}
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        hotel_point = (lat, lon)
        outbound = state.get("selected_transport") or {}
        arriving = arrival_point(outbound, "to") if outbound.get("record_kind") == "live_offer" else None
        if arriving:
            route = await asyncio.to_thread(get_transfer_router().route, arriving, hotel_point)
            if route:
                routes["arrival"] = route
        returning = state.get("selected_return_transport") or {}
        leaving = arrival_point(returning, "from") if returning.get("record_kind") == "live_offer" else None
        if leaving:
            route = await asyncio.to_thread(get_transfer_router().route, hotel_point, leaving)
            if route:
                routes["departure"] = route
    state["transfer_routes"] = routes
    return assemble_trip(state)


@lru_cache(maxsize=1)
def get_agent_orchestrator() -> AgentOrchestrator:
    catalog = AgentCatalogAdapter(get_catalog_gateway())
    return AgentOrchestrator(catalog=catalog)


async def handle_message(session_id: str, message: str, state: dict[str, Any]) -> AgentResponse:
    return await get_agent_orchestrator().handle_message(session_id, message, state)


async def handle_action(action: str, target_id: str, state: dict[str, Any],
                        message: str, *, catalog=None) -> AgentResponse:
    """Apply a card click by catalog ID; the LLM handles free-form chat only."""
    catalog = AgentCatalogAdapter(catalog or get_catalog_gateway())
    if action == "select_destination":
        destination = await catalog.get_destination(target_id)
        if not destination:
            return make_response("no_results", "Направление больше не найдено в каталоге.",
                                 state, message)
        updated = StateManager.update(state, TripPatch(
            city=destination["name"], destination_id=destination["destination_id"]))
        updated["stage"] = "selection"
        trip = updated["trip"]
        filters = SearchFilters.model_validate({
            key: value for key, value in trip.items()
            if key in SearchFilters.model_fields and value is not None
        })
        search = await search_hotels(SearchHotelsArgs(filters=filters), catalog, updated)
        hotels = search["hotels"]
        updated["last_hotel_ids"] = [str(item["hotel_id"]) for item in hotels]
        updated["last_hotel_offers"] = deepcopy(hotels)
        if not hotels:
            return make_response("no_results", f"Для города {destination['name']} отели по этим условиям не найдены.",
                                 updated, message)
        reply = (f"Город {destination['name']}: найдено {len(hotels)} вариантов размещения. "
                 "Откройте карточку отеля, чтобы выбрать его. "
                 "Цена и наличие указаны с пометкой источника.")
        return make_response("results", reply, updated, message, hotels=hotels,
                             warnings=search["warnings"])

    if action == "select_hotel":
        if target_id not in set(map(str, state.get("last_hotel_ids") or [])):
            return make_response("clarification", "Этот отель не входит в текущие результаты. Повторите поиск.",
                                 state, message)
        hotel = next((item for item in state.get("last_hotel_offers") or []
                      if str(item.get("hotel_id")) == target_id), None)
        if hotel is None:
            hotel = await catalog.get_hotel(target_id)
        if not hotel:
            return make_response("no_results", "Карточка отеля больше недоступна. Повторите поиск.",
                                 state, message)
        updated = deepcopy(state)
        trip = dict(updated.get("trip") or {})
        if not trip.get("city"):
            location = hotel.get("location") or {}
            city = hotel.get("city") or (location.get("city") if isinstance(location, dict) else None)
            if city:
                trip["city"] = city
                updated["trip"] = trip
        selected = dict(updated.get("selected") or {})
        if selected.get("hotel_offer_id") != target_id:
            updated["itinerary"] = None
            updated["cart"] = None
            clear_demo_booking(updated)
        selected["hotel_offer_id"] = target_id
        selected["hotel_name"] = hotel.get("name")
        updated["selected"] = selected
        updated["selected_hotel"] = hotel
        updated["transfer_routes"] = {}
        updated["stage"] = "selection"
        if updated.get("selected_transport"):
            updated = await assemble_with_transfers(updated)
        reply = (f"Выбран отель «{hotel.get('name') or target_id}». "
                 "Стоимость и наличие нужно сверить с источником перед бронированием. "
                 "Можете попросить меня найти дорогу на нужную дату.")
        warnings = (["Стоимость отеля — приблизительная оценка за ночь, не подтверждённая цена."]
                    if hotel.get("price_estimate") else [])
        return make_response("results", reply, updated, message, hotels=[hotel],
                             warnings=updated.get("warnings") or warnings)

    if action == "select_transport":
        option = next((item for item in state.get("last_transport_options") or []
                       if item.get("transport_id") == target_id), None)
        if not option:
            return make_response("clarification", "Этот вариант дороги устарел. Повторите поиск транспорта.",
                                 state, message)
        updated = deepcopy(state)
        selected = dict(updated.get("selected") or {})
        selected["outbound_transport_id"] = target_id
        updated["selected"] = selected
        updated["selected_transport"] = option
        updated["selected_return_transport"] = None
        updated["last_return_options"] = []
        selected["return_transport_id"] = None
        clear_demo_booking(updated)
        updated = await assemble_with_transfers(updated)
        reply = ("Маршрут и демонстрационная корзина собраны из выбранных вариантов. "
                 "Итог включает дорогу туда и проживание."
                 if updated.get("cart") else
                 "Дорога добавлена в маршрут. Для итоговой суммы нужны выбранный отель и точные даты проживания.")
        return make_response("results", reply, updated, message,
                             transport_options=[option], warnings=updated.get("warnings") or [])

    if action == "search_return_transport":
        trip = state.get("trip") or {}
        outbound = state.get("selected_transport") or {}
        try:
            return_day = date.fromisoformat(target_id)
            checkout_day = date.fromisoformat(trip["check_out"])
        except (ValueError, KeyError, TypeError):
            return make_response("clarification", "Укажите дату возвращения в формате ГГГГ-ММ-ДД.", state, message)
        if return_day < checkout_day:
            return make_response("clarification", "Обратная дорога должна быть не раньше выезда из отеля.", state, message)
        if not outbound or not trip.get("city") or not trip.get("origin_city"):
            return make_response("clarification", "Сначала выберите дорогу туда и город отправления.", state, message)
        updated = deepcopy(state)
        updated.setdefault("trip", {})["return_date"] = target_id
        updated["selected_return_transport"] = None
        updated.setdefault("selected", {})["return_transport_id"] = None
        updated["transfer_routes"] = {}
        clear_demo_booking(updated)
        options = await catalog.find_transport({
            "from_city": trip["city"], "to_city": trip["origin_city"],
            "date_from": target_id, "type": outbound.get("type"),
            "adults": trip.get("adults") or 1, "limit": 10,
        })
        options = [dict(option, trip_leg="return") for option in options]
        updated["last_return_options"] = options
        if not options:
            updated = await assemble_with_transfers(updated)
            return make_response("no_results", "Обратный билет на эту дату не найден. Его стоимость неизвестна.",
                                 updated, message, warnings=updated.get("warnings") or [])
        updated["itinerary"] = None
        updated["cart"] = None
        updated["stage"] = "planning"
        return make_response("results", f"Найдено {len(options)} вариантов обратной дороги на {target_id}.",
                             updated, message, transport_options=options)

    if action == "select_return_transport":
        option = next((item for item in state.get("last_return_options") or []
                       if item.get("transport_id") == target_id), None)
        if not option:
            return make_response("clarification", "Обратный вариант устарел. Повторите поиск.", state, message)
        updated = deepcopy(state)
        updated["selected_return_transport"] = option
        updated.setdefault("selected", {})["return_transport_id"] = target_id
        clear_demo_booking(updated)
        updated = await assemble_with_transfers(updated)
        return make_response("results", "Обратная дорога добавлена в маршрут.", updated, message,
                             transport_options=[option], warnings=updated.get("warnings") or [])

    raise ValueError(f"Unknown action: {action}")
