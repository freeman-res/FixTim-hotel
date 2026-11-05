from __future__ import annotations

import logging
import math
import os
import threading
import time

import httpx

log = logging.getLogger(__name__)

AIRPORTS = {
    "Казань": (55.6062, 49.2787),
    "Сочи": (43.4499, 39.9566),
    "Калининград": (54.8897, 20.5926),
    "Санкт-Петербург": (59.8003, 30.2625),
}


def arrival_point(option: dict, side: str) -> tuple[float, float] | None:
    point = option.get(side) or {}
    location = point.get("location") or point
    lat, lon = location.get("latitude"), location.get("longitude")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return (float(lat), float(lon))
    if option.get("type") == "plane":
        return AIRPORTS.get(point.get("city"))
    return None


class OsrmTransferRouter:
    _request_lock = threading.Lock()
    _last_request = 0.0

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("OSRM_URL", "https://router.project-osrm.org")).rstrip("/")
        if not self.base_url.startswith("https://"):
            raise ValueError("OSRM_URL must use HTTPS")
        self._cache: dict[tuple, tuple[float, dict]] = {}

    def route(self, start: tuple[float, float], end: tuple[float, float]) -> dict | None:
        coordinates = (*start, *end)
        if any(not isinstance(value, (int, float)) or not math.isfinite(value)
               for value in coordinates):
            return None
        if not (-90 <= start[0] <= 90 and -180 <= start[1] <= 180
                and -90 <= end[0] <= 90 and -180 <= end[1] <= 180):
            return None
        key = tuple(round(value, 5) for value in coordinates)
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < 86400:
            return dict(cached[1])
        url = (f"{self.base_url}/route/v1/driving/"
               f"{start[1]},{start[0]};{end[1]},{end[0]}")
        try:
            with self._request_lock:
                remaining = 1 - (time.monotonic() - type(self)._last_request)
                if remaining > 0:
                    time.sleep(remaining)
                type(self)._last_request = time.monotonic()
                response = httpx.get(url, params={"overview": "false"}, timeout=4,
                                     headers={"User-Agent": "OstrovokHackathon/1.0 (route planning demo)"})
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("code") != "Ok" or not payload.get("routes"):
                return None
            route = payload["routes"][0]
            distance = float(route["distance"]) / 1000
            duration = float(route["duration"]) / 60
            if not (0 < distance < 1000 and 0 < duration < 1440):
                return None
            result = {
                "distance_km": round(distance, 1),
                "duration_minutes": round(duration),
                "price_estimate_rub": max(400, round((300 + 35 * distance) / 50) * 50),
                "source": "OSRM", "price_kind": "estimate_not_booking_price",
            }
            self._cache[key] = (time.monotonic(), result)
            return dict(result)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, TimeoutError) as exc:
            log.info("OSRM route unavailable: %s", type(exc).__name__)
            return None
