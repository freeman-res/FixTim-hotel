"""Validate external MCP results before exposing them as current offers."""
from __future__ import annotations

import math
from datetime import datetime, timezone


def normalize_tutu_hotels(payload: dict, *, city: str, check_in: str, check_out: str,
                          required_amenities: list[str] | None = None) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    stay = payload.get("stay") or {}
    if stay.get("check_in") != check_in or stay.get("check_out") != check_out:
        return []
    nights = stay.get("nights")
    if not isinstance(nights, int) or nights <= 0:
        return []
    results = []
    for raw in payload.get("hotels") or []:
        if not isinstance(raw, dict) or not raw.get("hotel_id") or not raw.get("name"):
            continue
        offer = raw.get("best_offer") or {}
        price = offer.get("price") or {}
        amount = price.get("amount")
        url = offer.get("checkout_url") or raw.get("checkout_url")
        if (offer.get("price_basis") != "stay_total"
                or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0
                or price.get("currency") != "RUB" or not isinstance(url, str)
                or not url.startswith("https://hotel.tutu.ru/")):
            continue
        loc = raw.get("location") or {}
        rating_raw = raw.get("rating")
        rating = rating_raw / 2 if isinstance(rating_raw, (int, float)) and 0 <= rating_raw <= 10 else None
        results.append({
            "hotel_id": "tutu_" + str(raw["hotel_id"]),
            "external_hotel_id": str(raw["hotel_id"]),
            "record_kind": "live_offer", "name": raw["name"],
            "type": "hotel", "stars": raw.get("stars") or None,
            "rating": rating, "rating_source_scale": 10,
            "review_count": raw.get("review_count"),
            "location": {"city": city, "latitude": loc.get("lat"),
                         "longitude": loc.get("lng"), "address": raw.get("address")},
            "amenities": {item: True for item in (required_amenities or [])},
            "price": {"amount_min_rub": amount, "amount_max_rub": amount,
                      "total_amount": amount, "currency": "RUB", "unit": "per_stay",
                      "nights": nights, "scope": "date_specific_search_result"},
            "total_price": amount, "price_estimate": None,
            "availability": {"status": "unconfirmed", "note": "verify_final_room_availability_on_tutu"},
            "booking_url": url, "check_in": check_in, "check_out": check_out,
            "source": {"name": "Tutu MCP", "type": "live_search",
                       "retrieved_at": datetime.now(timezone.utc).isoformat(), "url": url},
            "is_demo": False,
        })
    return results
