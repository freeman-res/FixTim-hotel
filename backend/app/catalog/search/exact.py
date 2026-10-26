"""Точные фильтры по уже загруженным записям. Без I/O, без источников.
ТЗ№3 п.4: "Фильтровать только по фактам, доступным в источнике".
Поэтому, например, price-фильтр срабатывает только если у записи
price.amount_min есть. Иначе запись сохраняется ."""
from __future__ import annotations
import logging
from typing import Iterable
log = logging.getLogger(__name__)
def _pass_price_filter(price: dict | None, price_max: int | None,
                       price_min: int | None) -> bool:
    """ Если у записи price=None → НЕ отсекаем (правило «неизвестно ≠ нет»).
    Если price есть — сравниваем по минимальной сумме (optimistic)."""
    if price is None:
        return True
    amount = price.get("amount_min_rub") or price.get("amount_min") or price.get("amount")
    if amount is None:
        return True
    if price_max is not None and amount > price_max:
        return False
    if price_min is not None and amount < price_min:
        return False
    return True

def filter_hotels(hotels: Iterable[dict], filters: dict) -> list[dict]:
    city         = filters.get("city")
    hotel_ids    = set(filters.get("hotel_ids") or [])
    stars_min    = filters.get("stars_min")
    stars_max    = filters.get("stars_max")
    price_max    = filters.get("price_max")
    price_min    = filters.get("price_min")
    amenities    = filters.get("amenities") or {}
    require_price = bool(filters.get("require_price", False))

    out: list[dict] = []
    for h in hotels:
        if hotel_ids and h.get("hotel_id") not in hotel_ids:
            continue
        if city:
            loc_city = (h.get("location") or {}).get("city")
            if loc_city and loc_city != city:
                continue
        stars = h.get("stars")
        if stars_min is not None and stars is not None and stars < stars_min:
            continue
        if stars_max is not None and stars is not None and stars > stars_max:
            continue
        # Новое: явное «только с ценой»
        if require_price and h.get("price") is None:
            continue
        if not _pass_price_filter(h.get("price"), price_max, price_min):
            continue
        if amenities:
            h_am = h.get("amenities") or {}
            if any(h_am.get(k) != v for k, v in amenities.items()):
                continue
        out.append(h)
    return out


def filter_transport(options: Iterable[dict], filters: dict) -> list[dict]:
    t_type   = filters.get("type")           # plane | bus | train | None
    from_c   = filters.get("from_city")
    to_c     = filters.get("to_city")
    max_price = filters.get("max_price")
    date_from = filters.get("date_from")     # YYYY-MM-DD
    date_to   = filters.get("date_to")

    out: list[dict] = []
    for o in options:
        if t_type and o.get("type") != t_type:
            continue
        if from_c and (o.get("from") or {}).get("city") != from_c:
            continue
        if to_c and (o.get("to") or {}).get("city") != to_c:
            continue

        # Цена
        price = o.get("price") or {}
        amount = price.get("amount_min_rub") or price.get("amount_min")
        # Для авиарейсов цена None — фильтр по max_price такое отсекает,
        # только если пользователь ЯВНО просил цену. Иначе оставляем.
        if max_price is not None and amount is not None and amount > max_price:
            continue

        # Дата: у авиарейсов departure_utc, у автобусов schedule_date
        dep = o.get("departure_utc") or o.get("schedule_date") or ""
        dep_date = dep[:10] if dep else None
        if date_from and dep_date and dep_date < date_from:
            continue
        if date_to and dep_date and dep_date > date_to:
            continue

        out.append(o)
    return out
def filter_destinations(destinations: Iterable[dict], filters: dict) -> list[dict]:
    region       = filters.get("region")
    min_pop      = filters.get("min_population")
    dest_ids     = set(filters.get("destination_ids") or [])

    out: list[dict] = []
    for d in destinations:
        if dest_ids and d.get("destination_id") not in dest_ids:
            continue
        if region and d.get("region") != region:
            continue
        pop = d.get("population")
        if min_pop is not None and (pop is None or pop < min_pop):
            continue
        out.append(d)
    return out