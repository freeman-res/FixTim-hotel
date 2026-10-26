""" Геопоиск. Единственный корректный способ связать отель с городом."""
from __future__ import annotations
import math
from typing import Iterable
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Кратчайшее расстояние по поверхности Земли между двумя точками (км)."""
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def within_radius(
    records: Iterable[dict],
    center_lat: float,
    center_lon: float,
    radius_km: float,
    location_key: str = "location",
) -> list[dict]:
    """Оставляет записи, где (lat, lon) попадает в радиус.  Записи без координат отсекаются ."""
    out: list[dict] = []
    for r in records:
        loc = r.get(location_key) or {}
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat is None or lon is None:
            continue
        if haversine_km(center_lat, center_lon, lat, lon) <= radius_km:
            out.append(r)
    return out
def annotate_distance( records: Iterable[dict], center_lat: float, center_lon: float, out_key: str = "distance_from_center_km", location_key: str = "location",) -> list[dict]:
    """ Добавляет в каждую запись поле с расстоянием. Не отсекает. Используется, когда агент №2 хочет показать «отель в 2.3 км от центра». """
    out: list[dict] = []
    for r in records:
        loc = r.get(location_key) or {}
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat is None or lon is None:
            r2 = dict(r)
            r2[out_key] = None
        else:
            r2 = dict(r)
            r2[out_key] = round(haversine_km(center_lat, center_lon, lat, lon), 2)
        out.append(r2)
    return out