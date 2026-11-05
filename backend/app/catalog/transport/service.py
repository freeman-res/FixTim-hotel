"""Catalog transport search with optional Tutu aviation offers and labelled fallback."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from .rzd_provider import RzdTrainProvider
from ..pricing.estimates import estimate_transport_record, flight_estimate
from ..providers.base import CatalogProvider
from ..search.exact import filter_transport

log = logging.getLogger(__name__)


class TransportService:
    def __init__(self, provider: CatalogProvider, live_client=None):
        self.provider = provider
        self.live_client = live_client
        self._rzd = None

    def _live_flights(self, filters: dict) -> list[dict]:
        origin, destination, day = filters.get("from_city"), filters.get("to_city"), filters.get("date_from")
        if not self.live_client or not all((origin, destination, day)):
            return []
        try:
            payload = self.live_client.search_avia(
                origin=origin, destination=destination, date=day,
                adults=filters.get("adults") or 1, limit=filters.get("limit") or 10,
            )
        except Exception as exc:
            log.warning("Tutu flight search failed: %s", exc)
            return []
        if not isinstance(payload, dict):
            return []
        result = []
        for raw in payload.get("offers") or []:
            if not isinstance(raw, dict):
                continue
            price = raw.get("price") or {}
            amount = price.get("amount")
            dep = raw.get("departure_at")
            url = raw.get("search_results_url")
            if (not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0
                    or price.get("currency") != "RUB" or not isinstance(dep, str)
                    or dep[:10] != day or not isinstance(url, str)
                    or not url.startswith("https://avia.tutu.ru/")):
                continue
            try:
                departure_utc = datetime.fromisoformat(dep).astimezone(timezone.utc).isoformat()
                arrival = raw.get("arrival_at")
                arrival_utc = datetime.fromisoformat(arrival).astimezone(timezone.utc).isoformat() if arrival else None
            except ValueError:
                continue
            result.append({
                "transport_id": "tutu_avia_" + str(raw.get("offer_id") or len(result)),
                "record_kind": "live_offer", "type": "plane",
                "from": {"city": origin}, "to": {"city": destination},
                "schedule_date": day,
                "departure_utc": departure_utc, "arrival_utc": arrival_utc,
                "duration_minutes": raw.get("duration_min"),
                "airline": ", ".join(raw.get("carriers") or []),
                "segments_count": raw.get("segments_count"),
                "price": {"amount_min_rub": amount, "amount_max_rub": amount,
                          "currency": "RUB", "unit": "per_party_one_way",
                          "party_size": filters.get("adults") or 1},
                "price_estimate": None, "booking_url": url,
                "availability": {"status": "unconfirmed", "note": "verify_final_price_on_tutu"},
                "source": {"name": "Tutu MCP", "type": "live_search",
                           "retrieved_at": datetime.now(timezone.utc).isoformat(), "url": url},
                "is_demo": False,
            })
        return result

    def _estimated_flight(self, filters: dict) -> list[dict]:
        origin, destination, day = filters.get("from_city"), filters.get("to_city"), filters.get("date_from")
        if not all((origin, destination, day)):
            return []
        coords = {}
        for item in self.provider.load_destinations():
            loc = item.get("location") or {}
            if item.get("name") and isinstance(loc.get("latitude"), (int, float)) and isinstance(loc.get("longitude"), (int, float)):
                coords[item["name"]] = (loc["latitude"], loc["longitude"])
        load = getattr(self.provider, "load_flight_estimates", None)
        rows = load() if callable(load) else []
        stored = next((row.get("price_estimate") for row in rows
                       if row.get("from_city") == origin and row.get("to_city") == destination), None)
        estimate = dict(stored) if isinstance(stored, dict) else flight_estimate(origin, destination, coords, day)
        if estimate:
            estimate["date"] = day
        return [estimate_transport_record(origin, destination, day, estimate)] if estimate else []

    def _live_trains(self, filters: dict) -> list[dict]:
        if not self.live_client:
            return []
        origin, destination, day = filters["from_city"], filters["to_city"], filters["date_from"]
        try:
            payload = self.live_client.search_rail(
                origin=origin, destination=destination, date=day,
                passengers=filters.get("adults") or 1, limit=filters.get("limit") or 10,
            )
        except Exception as exc:
            log.warning("Tutu train search failed: %s", exc)
            return []
        if not isinstance(payload, dict):
            return []
        results = []
        for raw in payload.get("offers") or []:
            if not isinstance(raw, dict):
                continue
            price = raw.get("price") or {}
            amount, dep, url = price.get("amount"), raw.get("departure_at"), raw.get("search_results_url")
            if (not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0
                    or price.get("currency") != "RUB" or not isinstance(dep, str) or dep[:10] != day
                    or not isinstance(url, str) or not url.startswith("https://www.tutu.ru/poezda/")):
                continue
            try:
                departure_utc = datetime.fromisoformat(dep).astimezone(timezone.utc).isoformat()
                arrival = raw.get("arrival_at")
                arrival_utc = datetime.fromisoformat(arrival).astimezone(timezone.utc).isoformat() if arrival else None
            except ValueError:
                continue
            legs = raw.get("legs") or []
            segments = legs[0].get("segments") or [] if legs else []
            results.append({
                "transport_id": "tutu_rail_" + str(raw.get("offer_id") or len(results)),
                "record_kind": "live_offer", "type": "train",
                "from": {"city": origin}, "to": {"city": destination},
                "schedule_date": day, "departure_utc": departure_utc,
                "arrival_utc": arrival_utc, "duration_minutes": raw.get("duration_min"),
                "train_number": segments[0].get("voyage_no") if segments else None,
                "carrier": ", ".join(raw.get("carriers") or []),
                "price": {"amount_min_rub": amount, "amount_max_rub": amount,
                          "currency": "RUB", "unit": "per_person_one_way"},
                "price_estimate": None, "booking_url": url,
                "availability": {"status": "unconfirmed", "note": "verify_final_seats_and_price_on_tutu"},
                "source": {"name": "Tutu MCP", "type": "live_search",
                           "retrieved_at": datetime.now(timezone.utc).isoformat(), "url": url},
                "is_demo": False,
            })
        return results

    def find_transport(self, filters: dict) -> list[dict]:
        filters = filters or {}
        if filters.get("type") == "train":
            if not filters.get("from_city") or not filters.get("to_city") or not filters.get("date_from"):
                return []
            options = self._live_trains(filters)
            if not options:
                if self._rzd is None:
                    self._rzd = RzdTrainProvider()
                options = self._rzd.search(filters["from_city"], filters["to_city"], filters["date_from"])
        elif filters.get("type") == "plane" and filters.get("from_city") and filters.get("to_city"):
            options = self._live_flights(filters) or self._estimated_flight(filters)
        else:
            options = self.provider.load_transport()
        matched = filter_transport(options, filters)
        matched.sort(key=lambda t: (
            (t.get("price") or {}).get("amount_min_rub") is None,
            (t.get("price") or {}).get("amount_min_rub") or 0,
            t.get("departure_utc") or t.get("schedule_date") or "",
        ))
        log.info("find_transport: %d из %d вариантов после фильтров", len(matched), len(options))
        return matched
