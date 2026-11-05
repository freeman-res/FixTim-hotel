"""Daily weather forecast and clearly labelled historical monthly climate data."""
from __future__ import annotations

import logging
import math
import os
import time
from datetime import date, datetime, timedelta, timezone
from threading import RLock
from typing import Callable

import httpx

from ..providers.base import CatalogProvider

log = logging.getLogger(__name__)
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_MAX_DAYS = 16
FORECAST_CACHE_SECONDS = 1800
DAILY_VARIABLES = "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"


class ClimateService:
    def __init__(self, provider: CatalogProvider, *, client: httpx.Client | None = None,
                 today: Callable[[], date] | None = None):
        self.provider = provider
        self.client = client or httpx.Client(timeout=15)
        self.today = today or date.today
        self.enabled = os.getenv("CATALOG_CLIMATE_ENABLED", "1") == "1"
        self._cache: dict[tuple[str, int], tuple[float, dict]] = {}
        self._cache_lock = RLock()

    def _destination(self, destination_id: str) -> dict | None:
        return next((d for d in self.provider.load_destinations()
                     if d.get("destination_id") == destination_id), None)

    def _coordinates(self, destination_id: str) -> tuple[float, float] | None:
        destination = self._destination(destination_id)
        loc = (destination or {}).get("location") or {}
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if (not isinstance(lat, (int, float)) or not isinstance(lon, (int, float))
                or not math.isfinite(lat) or not math.isfinite(lon)
                or not -90 <= lat <= 90 or not -180 <= lon <= 180):
            return None
        return float(lat), float(lon)

    def get_climate(self, destination_id: str, month: int) -> dict | None:
        if (not self.enabled or not destination_id or not isinstance(month, int)
                or not 1 <= month <= 12):
            return None
        return next((row for row in self.provider.load_climate()
                     if row.get("destination_id") == destination_id and row.get("month") == month), None)

    def get_forecast(self, destination_id: str, days: int = 3,
                     target_date: str | None = None) -> dict | None:
        if not self.enabled or not destination_id or not isinstance(days, int) or not 1 <= days <= FORECAST_MAX_DAYS:
            return None
        coords = self._coordinates(destination_id)
        if coords is None:
            return None
        key = (destination_id, days)
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached and time.monotonic() - cached[0] < FORECAST_CACHE_SECONDS:
                result = cached[1]
            else:
                result = None
        if result is None:
            try:
                response = self.client.get(FORECAST_URL, params={
                    "latitude": coords[0], "longitude": coords[1],
                    "daily": DAILY_VARIABLES, "forecast_days": days,
                    "timezone": "auto",
                })
                response.raise_for_status()
                payload = response.json()
                daily = payload.get("daily") or {} if isinstance(payload, dict) else {}
                if not isinstance(daily, dict):
                    return None
                dates = daily.get("time") or []
                if not isinstance(dates, list) or not dates:
                    return None
                rows = []
                for i, day in enumerate(dates):
                    try:
                        rows.append({
                            "date": date.fromisoformat(day).isoformat(),
                            "temp_min_c": daily["temperature_2m_min"][i],
                            "temp_max_c": daily["temperature_2m_max"][i],
                            "precipitation_mm": daily["precipitation_sum"][i],
                            "weather_code": daily["weather_code"][i],
                        })
                    except (KeyError, IndexError, TypeError, ValueError):
                        continue
                if not rows:
                    return None
                result = {
                    "destination_id": destination_id,
                    "daily": rows,
                    "source": {"name": "Open-Meteo Forecast API", "type": "forecast_api",
                               "url": FORECAST_URL,
                               "retrieved_at": datetime.now(timezone.utc).isoformat()},
                    "note": "daily_forecast_up_to_16_days",
                    "is_demo": False,
                }
                with self._cache_lock:
                    self._cache[key] = (time.monotonic(), result)
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                log.warning("Open-Meteo forecast unavailable for %s: %s", destination_id, exc)
                return None
        if target_date:
            selected = [row for row in result["daily"] if row["date"] == target_date]
            return {**result, "daily": selected} if selected else None
        return result

    def get_expected_weather(self, destination_id: str, days_ahead: int) -> dict | None:
        if (not self.enabled or not destination_id or not isinstance(days_ahead, int)
                or days_ahead < 0):
            return None
        target = self.today() + timedelta(days=days_ahead)
        target_iso = target.isoformat()
        if days_ahead <= 5:
            forecast = self.get_forecast(destination_id, days=days_ahead + 1,
                                         target_date=target_iso)
            if forecast and forecast["daily"]:
                return {
                    "type": "exact_forecast", "target_date": target_iso,
                    "forecast": forecast["daily"][0], "source": forecast["source"],
                    "note": "forecast_not_guaranteed", "is_demo": False,
                }
        normal = self.get_climate(destination_id, target.month)
        if not normal or not isinstance(normal.get("temp_mean_c"), (int, float)):
            return None
        return {
            "type": "climate_estimate", "target_date": target_iso,
            "climate_normal_c": normal["temp_mean_c"],
            "expected_temp_c": normal["temp_mean_c"],
            "precipitation_mean_mm_per_day": normal.get("precipitation_mean_mm_per_day"),
            "source": normal["source"],
            "note": "historical_monthly_average_not_forecast", "is_demo": False,
        }
