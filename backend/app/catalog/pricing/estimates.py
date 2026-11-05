"""Deterministic planning estimates. These are never booking offers."""
from __future__ import annotations

import math
from datetime import datetime, timezone

CITY_BASELINES = {
    "Зеленоградск": 8900, "Сириус": 8300, "Казань": 7200,
    "Геленджик": 7000, "Нижний Новгород": 6900, "Сочи": 6700,
    "Кисловодск": 6400, "Санкт-Петербург": 6400, "Москва": 5900,
    "Калининград": 5600,
}
CITY_SOURCE = "https://www.kommersant.ru/doc/8512243"
CITY_PERIOD = "May-August 2026 bookings, Ostrovok city averages"
REGION_BASELINES = {
    "Ленинградская область": 14200, "Ставропольский край": 13300,
    "Московская область": 13100, "Краснодарский край": 11300,
    "Республика Крым": 10800, "Калининградская область": 10600,
    "Владимирская область": 10300, "Тюменская область": 10100,
    "Республика Татарстан": 9300, "Нижегородская область": 9100,
    "Ярославская область": 8900, "Челябинская область": 8800,
    "Москва": 8400, "Санкт-Петербург": 8300,
    "Приморский край": 8100, "Новосибирская область": 7800,
    "Свердловская область": 7700, "Самарская область": 7600,
    "Воронежская область": 7100, "Ростовская область": 6700,
}
REGION_SOURCE = "https://www.kommersant.ru/doc/9041364"
REGION_PERIOD = "January-September 2026, TravelLine regional averages"
NATIONAL_BASELINE = 6600
MAJOR_CITY_COORDS = {
    "Москва": (55.7558, 37.6173), "Санкт-Петербург": (59.9343, 30.3351),
    "Казань": (55.7961, 49.1064), "Сочи": (43.5855, 39.7231),
    "Калининград": (54.7104, 20.4522),
}
TYPE_FACTORS = {
    "hotel": 1.0, "guest_house": 0.75, "hostel": 0.38,
    "motel": 0.65, "apartment": 0.88, "aparthotel": 0.95,
    "resort": 1.2, "sanatorium": 1.0,
}
STAR_FACTORS = {1: 0.65, 2: 0.8, 3: 1.0, 4: 1.35, 5: 1.9}


def _rounded(value: float) -> int:
    return max(500, int(round(value / 100) * 100))


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(min(1.0, math.sqrt(a)))


def hotel_estimate(hotel: dict, region_by_city: dict[str, str] | None = None,
                   proxy_centers: list[dict] | None = None) -> dict:
    city = (hotel.get("location") or {}).get("city") or hotel.get("city")
    region = (region_by_city or {}).get(city)
    if city in CITY_BASELINES:
        baseline, source, period, basis = CITY_BASELINES[city], CITY_SOURCE, CITY_PERIOD, "city_average"
    elif region in REGION_BASELINES:
        baseline, source, period, basis = REGION_BASELINES[region], REGION_SOURCE, REGION_PERIOD, "region_average"
    elif proxy_centers and isinstance((hotel.get("location") or {}).get("latitude"), (int, float)) and isinstance((hotel.get("location") or {}).get("longitude"), (int, float)):
        loc = hotel["location"]
        nearby = []
        for center in proxy_centers:
            center_loc = center.get("location") or {}
            if (not isinstance(center_loc.get("latitude"), (int, float))
                    or not isinstance(center_loc.get("longitude"), (int, float))):
                continue
            if center.get("name") not in CITY_BASELINES and center.get("region") not in REGION_BASELINES:
                continue
            distance = _distance_km(loc["latitude"], loc["longitude"],
                                    center_loc["latitude"], center_loc["longitude"])
            if distance <= 120:
                nearby.append((distance, center))
        if nearby:
            distance, center = min(nearby, key=lambda pair: pair[0])
            if center.get("name") in CITY_BASELINES:
                baseline, source, period = CITY_BASELINES[center["name"]], CITY_SOURCE, CITY_PERIOD
            else:
                baseline, source, period = REGION_BASELINES[center["region"]], REGION_SOURCE, REGION_PERIOD
            basis = "nearby_city_proxy"
        else:
            baseline, source, period, basis = NATIONAL_BASELINE, CITY_SOURCE, CITY_PERIOD, "national_average"
    else:
        baseline, source, period, basis = NATIONAL_BASELINE, CITY_SOURCE, CITY_PERIOD, "national_average"
    hotel_type = str(hotel.get("type") or "").casefold()
    type_factor = TYPE_FACTORS.get(hotel_type, 0.9)
    stars = hotel.get("stars")
    star_factor = STAR_FACTORS.get(stars, 1.0)
    amenities = hotel.get("amenities") or {}
    amenity_factor = 1.0
    if isinstance(amenities, dict):
        for key, multiplier in (("pool", 1.12), ("spa", 1.1), ("breakfast", 1.06)):
            if amenities.get(key) is True:
                amenity_factor *= multiplier
    typical = _rounded(baseline * type_factor * star_factor * amenity_factor)
    result = {
        "kind": "synthetic_estimate", "amount_rub": typical,
        "range_min_rub": _rounded(typical * 0.7), "range_max_rub": _rounded(typical * 1.5),
        "currency": "RUB", "unit": "per_night", "basis": basis,
        "benchmark_rub": baseline, "benchmark_period": period,
        "benchmark_source_url": source, "method": "regional_average_x_type_x_stars_x_known_amenities",
        "hotel_type_factor": type_factor, "star_factor": star_factor,
        "availability": "unknown", "booking_url": None,
    }
    if basis == "nearby_city_proxy":
        result["proxy_city"] = center["name"]
        result["proxy_distance_km"] = round(distance)
    return result


def flight_estimate(origin: str, destination: str, coords_by_city: dict[str, tuple[float, float]],
                    date: str | None = None) -> dict | None:
    coords_by_city = {**MAJOR_CITY_COORDS, **coords_by_city}
    if origin == destination or origin not in coords_by_city or destination not in coords_by_city:
        return None
    lat1, lon1 = coords_by_city[origin]
    lat2, lon2 = coords_by_city[destination]
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    km = 6371 * 2 * math.asin(min(1.0, math.sqrt(a)))
    amount = _rounded(1800 + 3.6 * km)
    return {
        "kind": "synthetic_estimate", "amount_rub": amount,
        "range_min_rub": _rounded(amount * 0.65), "range_max_rub": _rounded(amount * 1.7),
        "currency": "RUB", "unit": "per_person_one_way", "date": date,
        "distance_km": round(km), "method": "1800_rub_plus_3_6_rub_per_great_circle_km",
        "basis": "geographic_distance_heuristic", "availability": "unknown",
        "booking_url": None, "warning": "Оценка не подтверждает существование рейса или наличие билетов.",
    }


def estimate_transport_record(origin: str, destination: str, date: str,
                              estimate: dict) -> dict:
    return {
        "transport_id": f"estimate_plane_{origin}_{destination}_{date}",
        "record_kind": "route_price_estimate", "type": "plane",
        "from": {"city": origin}, "to": {"city": destination},
        "schedule_date": date, "departure_utc": None, "arrival_utc": None,
        "price": None, "price_estimate": estimate, "booking_url": None,
        "availability": {"status": "unknown", "note": "synthetic_route_estimate_no_schedule"},
        "source": {"name": "Synthetic route model", "type": "synthetic_estimate",
                   "retrieved_at": datetime.now(timezone.utc).isoformat(), "url": None},
        "is_demo": True,
    }
