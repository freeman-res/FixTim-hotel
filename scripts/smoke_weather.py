"""Check climate fallback and report whether the live daily forecast responds."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.catalog.service import get_catalog_gateway


async def main() -> None:
    gateway = get_catalog_gateway()
    status = await gateway.get_data_status()
    cities = ("Москва", "Санкт-Петербург", "Казань", "Сочи", "Калининград")
    results = []
    live_count = 0
    for city in cities:
        today = await gateway.get_weather(city)
        november = await gateway.get_weather(city, month=11)
        current = today["weather"] if today else None
        if current and current.get("type") == "exact_forecast":
            live_count += 1
        results.append({
            "city": city,
            "today_weather": current,
            "live_forecast": bool(current and current.get("type") == "exact_forecast"),
            "november_normal": november["weather"] if november else None,
        })
    print(json.dumps({"climate_source": status["climate"], "cities": results},
                     ensure_ascii=False, indent=2))
    if not all(row["today_weather"] and row["november_normal"] for row in results):
        raise SystemExit("Weather smoke incomplete: today fallback or monthly normal missing")
    print(f"LIVE_FORECAST: {live_count}/{len(cities)} cities")
    if live_count == 0:
        print("WARN: live forecast unavailable; only historical climate fallback was verified")


if __name__ == "__main__":
    asyncio.run(main())
