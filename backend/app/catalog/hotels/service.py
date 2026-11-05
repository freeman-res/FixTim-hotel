
from __future__ import annotations

import logging
from datetime import date

from ..providers.base import CatalogProvider
from ..search.exact import filter_hotels
from ..search.geo import annotate_distance, within_radius
from ..live.normalize import normalize_tutu_hotels
from ..pricing.estimates import hotel_estimate

log = logging.getLogger(__name__)

DEFAULT_CITY_RADIUS_KM = 50.0


class HotelsService:
    """Синхронный сервис. Async-обёртку делает фасад catalog/service.py."""

    def __init__(self, provider: CatalogProvider, live_client=None):
        self.provider = provider
        self.live_client = live_client
        self._live_hotel_cache: dict[str, dict] = {}
        self._estimate_cache: dict[str, dict] | None = None

    def _estimate_for(self, hotel: dict, regions: dict[str, str], destinations: list[dict]) -> dict:
        if self._estimate_cache is None:
            load = getattr(self.provider, "load_hotel_estimates", None)
            rows = load() if callable(load) else []
            self._estimate_cache = {row["hotel_id"]: row for row in rows if isinstance(row, dict) and row.get("hotel_id")}
        row = self._estimate_cache.get(hotel.get("hotel_id"))
        if (row and row.get("name") == hotel.get("name")
                and row.get("city") == (hotel.get("location") or {}).get("city")
                and isinstance(row.get("price_estimate"), dict)):
            return row["price_estimate"]
        return hotel_estimate(hotel, regions, destinations)

    def _with_estimate(self, hotel: dict, destinations: list[dict] | None = None,
                       regions: dict[str, str] | None = None) -> dict:
        item = dict(hotel)
        if item.get("price") is None:
            destinations = destinations if destinations is not None else self.provider.load_destinations()
            regions = regions if regions is not None else {d.get("name"): d.get("region") for d in destinations}
            item["price_estimate"] = self._estimate_for(item, regions, destinations)
            item["record_kind"] = "catalog_with_estimate"
        else:
            item["price_estimate"] = None
        return item

    def _live_offers(self, filters: dict) -> list[dict]:
        city, check_in, check_out = filters.get("city"), filters.get("check_in"), filters.get("check_out")
        if not self.live_client or not all((city, check_in, check_out)):
            return []
        if filters.get("hotel_ids") or filters.get("near"):
            return []
        try:
            nights = (date.fromisoformat(check_out) - date.fromisoformat(check_in)).days
            if nights <= 0:
                return []
            requested = [str(x).casefold() for x in (filters.get("required_amenities") or [])]
            supported = {"wifi", "parking", "pool", "spa", "pets", "sauna", "gym", "kids"}
            aliases = {"internet": "wifi", "wi-fi": "wifi", "интернет": "wifi", "парковка": "parking"}
            api_amenities = [aliases.get(x, x) for x in requested]
            if any(x not in supported for x in api_amenities):
                return []
            budget = filters.get("max_total_price")
            nightly_cap = int(float(budget) / nights) if budget is not None else None
            if filters.get("price_max") is not None:
                nightly_cap = min(nightly_cap, int(filters["price_max"])) if nightly_cap is not None else int(filters["price_max"])
            payload = self.live_client.search_hotels(
                city=city, check_in=check_in, check_out=check_out,
                adults=filters.get("adults") or filters.get("guests") or 1,
                limit=filters.get("limit") or 10,
                hotel_amenities=api_amenities,
                price_max=nightly_cap,
            )
            offers = normalize_tutu_hotels(payload, city=city, check_in=check_in,
                                           check_out=check_out, required_amenities=requested)
            if filters.get("stars_min") is not None:
                offers = [h for h in offers if h.get("stars") is not None and h["stars"] >= filters["stars_min"]]
            if filters.get("stars_max") is not None:
                offers = [h for h in offers if h.get("stars") is not None and h["stars"] <= filters["stars_max"]]
            if filters.get("max_total_price") is not None:
                offers = [h for h in offers if h["total_price"] <= filters["max_total_price"]]
            if filters.get("price_max") is not None:
                offers = [h for h in offers if h["total_price"] / nights <= filters["price_max"]]
            if filters.get("price_min") is not None:
                offers = [h for h in offers if h["total_price"] / nights >= filters["price_min"]]
            for hotel in offers:
                self._live_hotel_cache[hotel["hotel_id"]] = hotel
            return offers
        except Exception as exc:
            log.warning("Tutu hotel search failed: %s", exc)
            return []





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





    def find_offers(self, filters: dict) -> list[dict]:
        filters = filters or {}
        live = self._live_offers(filters)
        if live:
            return live
        hotels = self.provider.load_hotels()

        near = filters.get("near") if isinstance(filters, dict) else None
        city = filters.get("city") if isinstance(filters, dict) else None


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

        destinations = self.provider.load_destinations()
        regions = {d.get("name"): d.get("region") for d in destinations}
        matched = [self._with_estimate(h, destinations, regions) for h in matched]
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
        if hotel_id in self._live_hotel_cache:
            return self._live_hotel_cache[hotel_id]
        for h in self.provider.load_hotels():
            if h.get("hotel_id") == hotel_id:
                return self._with_estimate(h)
        return None

    def get_hotels_by_ids(self, hotel_ids: list[str]) -> list[dict]:
        if not hotel_ids:
            return []
        wanted = set(hotel_ids)
        result = [
            h for h in self.provider.load_hotels()
            if h.get("hotel_id") in wanted
        ]
        destinations = self.provider.load_destinations()
        regions = {d.get("name"): d.get("region") for d in destinations}
        by_id = {h["hotel_id"]: self._with_estimate(h, destinations, regions) for h in result}
        by_id.update(self._live_hotel_cache)
        return [by_id[i] for i in hotel_ids if i in by_id]
