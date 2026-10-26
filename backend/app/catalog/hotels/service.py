"""
catalog/hotels/service.py
=========================
Структурированный поиск отелей. ТЗ№3 п.4.

Контракт с №2 (п.6):
    find_offers(filters)          -> list[dict]
    get_hotel(hotel_id)           -> dict | None
    get_hotels_by_ids(hotel_ids)  -> list[dict]

Гео-логика:
    1. filters['near'] = {lat, lon, radius_km} — строгий радиус.
    2. filters['city'] — OR: location.city == city ИЛИ в радиусе 50 км
       от центра города (центр из destinations.json).
    3. Нет ни near, ни city — только exact-фильтры.
"""

from __future__ import annotations

import logging

from ..providers.base import CatalogProvider
from ..search.exact import filter_hotels
from ..search.geo import annotate_distance, within_radius

log = logging.getLogger(__name__)

DEFAULT_CITY_RADIUS_KM = 50.0


class HotelsService:
    """Синхронный сервис. Async-обёртку делает фасад catalog/service.py."""

    def __init__(self, provider: CatalogProvider):
        self.provider = provider

    # ------------------------------------------------------------------------
    # Внутренние хелперы
    # ------------------------------------------------------------------------

    def _find_city_center(self, city_name: str) -> tuple[float, float] | None:
        """Ищет координаты города в destinations.json. None — если не нашли."""
        if not city_name:
            return None
        for d in self.provider.load_destinations():
            if d.get("name") == city_name:
                loc = d.get("location") or {}
                lat, lon = loc.get("latitude"), loc.get("longitude")
                if lat is not None and lon is not None:
                    return float(lat), float(lon)
        return None

    # ------------------------------------------------------------------------
    # Публичные методы (контракт с №2)
    # ------------------------------------------------------------------------

    def find_offers(self, filters: dict) -> list[dict]:
        hotels = self.provider.load_hotels()

        near = filters.get("near") if isinstance(filters, dict) else None
        city = filters.get("city") if isinstance(filters, dict) else None

        # exact-фильтры без city/near — их обработаем ниже
        filters_for_exact = dict(filters)
        filters_for_exact.pop("near", None)
        filters_for_exact.pop("city", None)
        matched = filter_hotels(hotels, filters_for_exact)

        if near and all(
            isinstance(near.get(k), (int, float)) for k in ("lat", "lon")
        ):
            radius = float(near.get("radius_km", DEFAULT_CITY_RADIUS_KM))
            matched = within_radius(matched, near["lat"], near["lon"], radius)
            matched = annotate_distance(matched, near["lat"], near["lon"])

        elif city:
            center = self._find_city_center(city)
            if center:
                in_radius_ids = {
                    h["hotel_id"]
                    for h in within_radius(
                        matched, center[0], center[1], DEFAULT_CITY_RADIUS_KM
                    )
                }
                matched = [
                    h for h in matched
                    if h["hotel_id"] in in_radius_ids
                    or (h.get("location") or {}).get("city") == city
                ]
                matched = annotate_distance(matched, center[0], center[1])
                log.info("find_offers: city='%s' geo+field, %d отелей",
                         city, len(matched))
            else:
                matched = [
                    h for h in matched
                    if (h.get("location") or {}).get("city") == city
                ]
                log.info("find_offers: city='%s' только по полю, %d отелей",
                         city, len(matched))

        matched.sort(key=lambda h: (
            h.get("price") is None,
            -(h.get("stars") or 0),
            (h.get("name") or "").lower(),
        ))
        log.info("find_offers: %d из %d отелей после фильтров",
                 len(matched), len(hotels))
        return matched

    def get_hotel(self, hotel_id: str) -> dict | None:
        if not hotel_id:
            return None
        for h in self.provider.load_hotels():
            if h.get("hotel_id") == hotel_id:
                return h
        return None

    def get_hotels_by_ids(self, hotel_ids: list[str]) -> list[dict]:
        if not hotel_ids:
            return []
        wanted = set(hotel_ids)
        result = [
            h for h in self.provider.load_hotels()
            if h.get("hotel_id") in wanted
        ]
        by_id = {h["hotel_id"]: h for h in result}
        return [by_id[i] for i in hotel_ids if i in by_id]