"""Normalize CatalogGateway records and filters at the Agent boundary."""

from __future__ import annotations

from typing import Any


_AMENITY_ALIASES = {
    "wifi": "internet",
    "wi-fi": "internet",
    "wi fi": "internet",
    "интернет": "internet",
    "парковка": "parking",
}
_TRUE_VALUES = {"yes", "true", "1", "да", "wlan", "wifi", "available"}


def _has_evidence(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in _TRUE_VALUES
    return False


def normalize_hotel(record: dict[str, Any]) -> dict[str, Any]:
    """Keep the catalog record intact and add the flat fields Agent №2 ranks."""
    hotel = dict(record)
    location = record.get("location")
    location = dict(location) if isinstance(location, dict) else {}
    amenity_data = record.get("amenities")
    amenity_data = dict(amenity_data) if isinstance(amenity_data, dict) else {}
    if isinstance(record.get("amenities"), list):
        amenities = [str(item).strip().casefold() for item in record["amenities"] if str(item).strip()]
    else:
        amenities = []
        for key, value in amenity_data.items():
            if _has_evidence(value):
                original = str(key).casefold()
                canonical = _AMENITY_ALIASES.get(original, original)
                amenities.append(canonical)
                if canonical == "internet":
                    amenities.extend(("wifi", "wi-fi", "интернет"))
                elif canonical == "parking":
                    amenities.append("парковка")

    price_data = record.get("price")
    price_data = dict(price_data) if isinstance(price_data, dict) else None
    total_price = record.get("total_price")
    if total_price is None and price_data:

        if price_data.get("unit") in (None, "total", "per_stay"):
            total_price = price_data.get("total_amount") or price_data.get("amount_total")

    hotel.update({
        "city": location.get("city") or record.get("city"),
        "address": location.get("address") or record.get("address"),
        "location": location or record.get("location"),
        "stars": record.get("stars"),
        "rating": record.get("rating"),
        "amenities": amenities,
        "amenities_data": amenity_data,
        "price": price_data,
        "total_price": total_price,
        "currency": (price_data or {}).get("currency") or record.get("currency"),
        "availability": record.get("availability") or {"status": "unknown"},
        "source": record.get("source"),
        "is_demo": bool(record.get("is_demo", False)),
    })
    return hotel


def _has_required_amenity(hotel: dict[str, Any], requested: str) -> bool:
    term = requested.strip().casefold()
    key = _AMENITY_ALIASES.get(term, term)
    if key in hotel.get("amenities", []):
        return True
    evidence = hotel.get("amenities_data") or {}
    return _has_evidence(evidence.get(key))


class AgentCatalogAdapter:
    """Translate Agent filters and normalize Catalog records without inventing facts."""

    def __init__(self, catalog):
        self.catalog = catalog

    async def find_offers(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        filters = filters or {}
        catalog_filters: dict[str, Any] = {}
        for key in ("city", "hotel_ids", "near", "stars_min", "stars_max",
                    "check_in", "check_out", "guests", "adults", "required_amenities",
                    "max_total_price"):
            if filters.get(key) is not None:
                catalog_filters[key] = filters[key]

        raw = await self.catalog.find_offers(catalog_filters)
        if isinstance(raw, dict):
            raw = raw.get("offers", raw.get("hotels", []))
        if not isinstance(raw, list):
            return []
        hotels = [normalize_hotel(item) for item in raw if isinstance(item, dict)]
        if catalog_filters.get("city"):
            for hotel in hotels:

                hotel["catalog_city_filter_applied"] = True
        required = [str(item) for item in filters.get("required_amenities", [])]
        if required:
            hotels = [hotel for hotel in hotels
                      if all(_has_required_amenity(hotel, item) for item in required)]
        return hotels

    async def get_hotel(self, hotel_id: str) -> dict[str, Any] | None:
        record = await self.catalog.get_hotel(hotel_id)
        return normalize_hotel(record) if isinstance(record, dict) else None

    async def get_hotels_by_ids(self, hotel_ids: list[str]) -> list[dict[str, Any]]:
        records = await self.catalog.get_hotels_by_ids(hotel_ids)
        return [normalize_hotel(item) for item in records if isinstance(item, dict)]

    async def retrieve_reviews(self, query: str, hotel_ids: list[str], top_k: int = 5) -> list[dict]:

        return await self.catalog.retrieve_reviews(query, hotel_ids, top_k)

    async def retrieve_descriptions(self, query: str, hotel_ids: list[str], top_k: int = 5) -> list[dict]:
        method = getattr(self.catalog, "retrieve_descriptions", None)
        if not callable(method):
            return []
        return await method(query, hotel_ids, top_k)

    async def find_transport(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        method = getattr(self.catalog, "find_transport", None)
        if not callable(method):
            return []
        return await method(filters)

    def __getattr__(self, name: str):

        return getattr(self.catalog, name)
