from __future__ import annotations

from copy import deepcopy
from datetime import date
import math


def _positive(value) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0:
        return float(value)
    return None


def _hotel_amount(hotel: dict, nights: int) -> tuple[float, bool] | None:
    total = _positive(hotel.get("total_price"))
    if total is not None and hotel.get("currency") in (None, "RUB"):
        return total, hotel.get("record_kind") != "live_offer"
    estimate = hotel.get("price_estimate") or {}
    nightly = _positive(estimate.get("amount_rub"))
    if nightly is not None and estimate.get("unit") == "per_night":
        return nightly * nights, True
    return None


def _transport_amount(option: dict, adults: int) -> tuple[float, bool] | None:
    if option.get("record_kind") == "live_offer":
        price = option.get("price") or {}
        amount = _positive(price.get("amount_min_rub"))
        if amount is None or price.get("currency") != "RUB":
            return None
        unit = price.get("unit")
        if unit == "per_party_one_way" and price.get("party_size") == adults:
            return amount, False
        if unit == "per_person_one_way":
            return amount * adults, False
        return None
    estimate = option.get("price_estimate") or {}
    amount = _positive(estimate.get("amount_rub"))
    if amount is not None and estimate.get("unit") == "per_person_one_way":
        return amount * adults, True
    return None


def assemble_trip(state: dict) -> dict:
    result = deepcopy(state)
    trip = result.get("trip") or {}
    hotel = result.get("selected_hotel") or {}
    transport = result.get("selected_transport") or {}
    return_transport = result.get("selected_return_transport") or {}
    transfer_routes = result.get("transfer_routes") or {}
    legs = []
    warnings = []
    if transport:
        origin = (transport.get("from") or {}).get("city") or trip.get("origin_city") or "Отправление"
        destination = (transport.get("to") or {}).get("city") or trip.get("city") or "прибытие"
        estimated = transport.get("record_kind") != "live_offer"
        legs.append({
            "type": {"plane": "flight", "train": "train", "bus": "bus"}.get(transport.get("type"), "transport"),
            "title": f"{origin} → {destination}",
            "detail": "Маршрут по выбранным условиям" if estimated else "Предложение из поиска",
            "time": transport.get("departure_utc") or transport.get("schedule_date"),
            "transport_id": transport.get("transport_id"),
        })
        if estimated:
            warnings.append("Для дороги есть только оценка стоимости; существование рейса не подтверждено.")
    if hotel:
        check_in, check_out = trip.get("check_in"), trip.get("check_out")
        dates = f"{check_in} — {check_out}" if check_in and check_out else "Даты проживания не уточнены"
        legs.append({"type": "hotel", "title": hotel.get("name") or "Отель",
                     "detail": dates, "time": check_in, "hotel_id": hotel.get("hotel_id")})
        if hotel.get("price_estimate") or hotel.get("record_kind") != "live_offer":
            warnings.append("Наличие номера и итоговая стоимость отеля не подтверждены.")
    if return_transport:
        origin = (return_transport.get("from") or {}).get("city") or trip.get("city") or "Отправление"
        destination = (return_transport.get("to") or {}).get("city") or trip.get("origin_city") or "прибытие"
        legs.append({"type": {"plane": "flight", "train": "train", "bus": "bus"}.get(return_transport.get("type"), "transport"),
                     "title": f"Обратно: {origin} → {destination}", "detail": "Выбранный обратный маршрут",
                     "time": return_transport.get("departure_utc") or trip.get("return_date"),
                     "transport_id": return_transport.get("transport_id")})
    for direction, title in (("arrival", "От точки прибытия до отеля"),
                             ("departure", "От отеля до точки отправления")):
        route = transfer_routes.get(direction)
        if route:
            legs.append({"type": "transfer", "title": title,
                         "detail": f"{route['distance_km']} км, около {route['duration_minutes']} мин"})
    if not legs:
        result["itinerary"] = None
        result["cart"] = None
        result["warnings"] = []
        return result

    result["itinerary"] = {"legs": legs, "is_partial": True}
    result["stage"] = "planning"
    result["cart"] = None
    if not return_transport:
        warnings.append("Обратная дорога пока не выбрана; общая стоимость поездки неизвестна.")
    if not hotel or not transport:
        warnings.append("Для корзины нужно выбрать и отель, и дорогу.")
        result["warnings"] = warnings
        return result
    try:
        nights = (date.fromisoformat(trip["check_out"]) -
                  date.fromisoformat(trip["check_in"])).days
    except (KeyError, TypeError, ValueError):
        nights = 0
    if nights <= 0:
        warnings.append("Нужны точные даты заезда и выезда для расчёта проживания.")
        result["warnings"] = warnings
        return result
    adults = trip.get("adults") or trip.get("guests") or 1
    if not isinstance(adults, int) or adults < 1:
        adults = 1
    hotel_price = _hotel_amount(hotel, nights)
    transport_price = _transport_amount(transport, adults)
    if hotel_price is None or transport_price is None:
        warnings.append("Итог нельзя рассчитать: не хватает сопоставимых цен в рублях.")
        result["warnings"] = warnings
        return result
    hotel_amount, hotel_estimated = hotel_price
    transport_amount, transport_estimated = transport_price
    items = [
        {"type": "transport", "name": f"Дорога туда: {legs[0]['title']}",
         "price": transport_amount, "currency": "RUB", "estimated": transport_estimated},
        {"type": "hotel", "name": f"{hotel.get('name') or 'Отель'}, {nights} ноч.",
         "price": hotel_amount, "currency": "RUB", "estimated": hotel_estimated},
    ]
    return_price = _transport_amount(return_transport, adults) if return_transport else None
    items.append({"type": "return_transport", "name": "Обратная дорога",
                  "price": return_price[0] if return_price else None,
                  "currency": "RUB", "estimated": return_price[1] if return_price else False})
    for direction, title in (("arrival", "Трансфер до отеля"),
                             ("departure", "Трансфер от отеля")):
        route = transfer_routes.get(direction)
        if route:
            items.append({"type": "transfer", "name": title,
                          "price": route["price_estimate_rub"], "currency": "RUB",
                          "estimated": True, "distance_km": route["distance_km"]})
    known_total = sum(item["price"] for item in items if item["price"] is not None)
    complete = bool(return_price and transfer_routes.get("arrival") and transfer_routes.get("departure"))
    result["cart"] = {
        "items": items,
        "total": round(known_total, 2), "currency": "RUB",
        "scope": "round_trip_with_transfers" if complete else "outbound_transport_and_hotel_only",
        "complete": complete,
        "has_estimates": any(item["estimated"] for item in items),
        "is_demo": True,
    }
    result["stage"] = "checkout"
    result["warnings"] = warnings
    return result
