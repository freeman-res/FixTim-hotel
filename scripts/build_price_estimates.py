"""Generate labelled planning estimates for current hotel catalog and route coverage.

Run from project root: python scripts/build_price_estimates.py
The generated amounts are not offers, availability, or date-specific tariffs.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.catalog.pricing.estimates import (
    CITY_SOURCE, REGION_SOURCE, flight_estimate, hotel_estimate,
)


def _read(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build(data_dir: Path = ROOT / "data" / "catalog") -> dict:
    hotels_path = data_dir / "hotels.json"
    hotels = _read(hotels_path)
    destinations = _read(data_dir / "destinations.json")
    transport = _read(data_dir / "transport_options.json")
    regions = {d.get("name"): d.get("region") for d in destinations}
    coords = {
        d["name"]: (d["location"]["latitude"], d["location"]["longitude"])
        for d in destinations
        if d.get("name") and isinstance((d.get("location") or {}).get("latitude"), (int, float))
        and isinstance((d.get("location") or {}).get("longitude"), (int, float))
    }
    hotel_rows = [
        {"hotel_id": h["hotel_id"], "name": h.get("name"),
         "city": (h.get("location") or {}).get("city"),
         "price_estimate": hotel_estimate(h, regions, destinations)}
        for h in hotels if h.get("hotel_id")
    ]
    routes = {
        ((t.get("from") or {}).get("city"), (t.get("to") or {}).get("city"))
        for t in transport if t.get("type") == "plane"
    }
    routes.update({("Москва", "Казань"), ("Москва", "Сочи"),
                   ("Санкт-Петербург", "Калининград")})
    route_rows = []
    for origin, destination in sorted((a, b) for a, b in routes if a and b):
        estimate = flight_estimate(origin, destination, coords)
        if estimate:
            route_rows.append({"from_city": origin, "to_city": destination,
                               "price_estimate": estimate})
    _write(data_dir / "hotel_price_estimates.json", hotel_rows)
    _write(data_dir / "flight_route_price_estimates.json", route_rows)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hotel_catalog_sha256": hashlib.sha256(hotels_path.read_bytes()).hexdigest(),
        "hotel_estimate_count": len(hotel_rows), "flight_route_estimate_count": len(route_rows),
        "hotel_benchmark_urls": [CITY_SOURCE, REGION_SOURCE],
        "warning": "Synthetic planning estimates; never treat as bookable offers or actual prices.",
    }
    (data_dir / "price_estimates_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
