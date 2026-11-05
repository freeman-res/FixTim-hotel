"""Merge prepared hotel datasets into the runtime catalog without inventing prices."""
from __future__ import annotations

import copy
import gzip
import json
import logging
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


log = logging.getLogger(__name__)

METADATA_FILE = "booking_hotels_ru.jsonl.gz"
PRICE_FILE = "hotel_price_references.jsonl.gz"
METADATA_MATCH_METERS = 50.0
DUPLICATE_CANDIDATE_METERS = 100.0
_GRID_SCALE = 100


def _normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(char for char in text if char.isalnum())


def _normalize_city(value: Any, aliases: dict[str, str]) -> str | None:
    text = " ".join(str(value or "").split())
    if not text:
        return None
    return aliases.get(text.casefold(), text)


def _coordinates(record: dict) -> tuple[float, float] | None:
    location = record.get("location") or {}
    try:
        latitude = float(location["latitude"])
        longitude = float(location["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude


def _distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    haversine = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 12_742_000 * math.asin(min(1.0, math.sqrt(haversine)))


def _grid_bucket(coordinates: tuple[float, float]) -> tuple[int, int]:
    return (math.floor(coordinates[0] * _GRID_SCALE),
            math.floor(coordinates[1] * _GRID_SCALE))


def _read_jsonl_gz(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    records: list[dict] = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise ValueError(f"{path.name}:{line_number} must be a JSON object")
                records.append(item)
    except Exception as exc:
        raise ValueError(f"Cannot read prepared hotel source {path}: {exc}") from exc
    return records


def _source_detail(record: dict, match_status: str,
                   duplicate_candidates: list[str] | None = None) -> dict:
    fields = (
        "description", "attractions", "facilities_text", "amenities",
        "amenities_source", "amenity_labels", "guest_rating", "source_metrics",
        "source_flags",
    )
    detail = {
        "source_record_id": record.get("source_record_id"),
        "record_type": record.get("record_type"),
        "source": copy.deepcopy(record.get("source") or {}),
        "match_status": match_status,
    }
    if duplicate_candidates:
        detail["possible_duplicate_candidate_ids"] = sorted(set(duplicate_candidates))
    detail.update({key: copy.deepcopy(record[key]) for key in fields if record.get(key) is not None})
    return detail


def _append_text(existing: Any, addition: Any) -> str | None:
    left = " ".join(str(existing or "").split())
    right = " ".join(str(addition or "").split())
    if not right or right.casefold() in left.casefold():
        return left or None
    if not left:
        return right
    return f"{left} | {right}"


def _attach_source(target: dict, record: dict, match_status: str,
                   duplicate_candidates: list[str] | None = None) -> None:
    detail = _source_detail(record, match_status, duplicate_candidates)
    target.setdefault("source_details", [])
    source_id = detail.get("source_record_id")
    if not any(item.get("source_record_id") == source_id for item in target["source_details"]):
        target["source_details"].append(detail)

    for key in ("description", "attractions", "facilities_text"):
        if record.get(key):
            target[key] = _append_text(target.get(key), record[key])
    if record.get("search_text"):
        target["search_text"] = _append_text(target.get("search_text"), record["search_text"])

    existing_amenities = target.get("amenities")
    if not isinstance(existing_amenities, dict):
        existing_amenities = {}
        target["amenities"] = existing_amenities
    for key, value in (record.get("amenities") or {}).items():
        if key not in existing_amenities or existing_amenities[key] is None:
            existing_amenities[key] = value
    labels = target.setdefault("amenity_labels", [])
    if isinstance(labels, list):
        for label in record.get("amenity_labels") or []:
            if label not in labels:
                labels.append(label)

    for key in ("guest_rating", "source_metrics", "source_flags"):
        if target.get(key) is None and record.get(key) is not None:
            target[key] = copy.deepcopy(record[key])



    if target.get("stars") is None and record.get("stars") is not None:
        target["stars"] = record["stars"]
    target_location = target.setdefault("location", {})
    source_location = record.get("location") or {}
    if isinstance(target_location, dict) and isinstance(source_location, dict):
        for key in ("address", "latitude", "longitude"):
            if target_location.get(key) is None and source_location.get(key) is not None:
                target_location[key] = source_location[key]
    if record.get("contacts"):
        contacts = target.setdefault("contacts", {})
        if isinstance(contacts, dict):
            for key, value in record["contacts"].items():
                if contacts.get(key) is None and value is not None:
                    contacts[key] = copy.deepcopy(value)

    references = record.get("price_references") or []
    if references:
        target.setdefault("price_references", [])
        target["price_references"].extend(copy.deepcopy(references))


def _build_indexes(hotels: list[dict]):
    by_name: dict[str, list[dict]] = defaultdict(list)
    spatial: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for hotel in hotels:
        key = _normalize_name(hotel.get("name"))
        if key:
            by_name[key].append(hotel)
        coordinates = _coordinates(hotel)
        if coordinates:
            spatial[_grid_bucket(coordinates)].append(hotel)
    return by_name, spatial


def _nearby_ids(coordinates: tuple[float, float] | None,
                spatial: dict[tuple[int, int], list[dict]], threshold_m: float) -> list[str]:
    if coordinates is None:
        return []
    bucket_lat, bucket_lon = _grid_bucket(coordinates)
    found: list[str] = []
    for lat_offset in (-1, 0, 1):
        for lon_offset in (-1, 0, 1):
            for candidate in spatial.get((bucket_lat + lat_offset, bucket_lon + lon_offset), []):
                candidate_coordinates = _coordinates(candidate)
                if candidate_coordinates and _distance_m(coordinates, candidate_coordinates) <= threshold_m:
                    found.append(str(candidate.get("hotel_id")))
    return sorted(set(found))


def _prepare_location(record: dict, city_aliases: dict[str, str]) -> None:
    location = record.setdefault("location", {})
    if isinstance(location, dict):
        raw_city = location.get("city")
        canonical_city = _normalize_city(raw_city, city_aliases)
        if canonical_city:
            location["city"] = canonical_city


def _append_source_record(hotels: list[dict], record: dict,
                          duplicate_candidates: list[str],
                          used_ids: set[str]) -> dict:
    appended = copy.deepcopy(record)
    source_id = str(appended.get("source_record_id") or "source_record")
    hotel_id = source_id
    suffix = 2
    while hotel_id in used_ids:
        hotel_id = f"{source_id}__{suffix}"
        suffix += 1
    appended["hotel_id"] = hotel_id
    appended.setdefault("price", None)
    appended.setdefault("availability", {
        "status": "unknown",
        "note": "static_source_record_does_not_confirm_live_availability",
    })
    appended["data_quality"] = {
        "identity_status": "source_record_only",
        "possible_duplicate_candidate_ids": sorted(set(duplicate_candidates)),
    }
    hotels.append(appended)
    used_ids.add(hotel_id)
    return appended


def _price_source_city(record: dict, aliases: dict[str, str]) -> str | None:
    location = record.get("location") or {}
    if location.get("city_evidence") != "explicit_description":
        return None
    return _normalize_city(location.get("city"), aliases)


def load_prepared_hotel_sources(
    base_hotels: list[dict],
    source_dir: Path,
    city_aliases: dict[str, str] | None = None,
) -> tuple[list[dict], dict[str, int]]:
    """Merge prepared sources conservatively and keep source-only records searchable."""
    aliases = {str(key).casefold(): str(value) for key, value in (city_aliases or {}).items()}
    hotels = copy.deepcopy(base_hotels)
    used_ids = {str(item.get("hotel_id")) for item in hotels}
    metadata_records = _read_jsonl_gz(Path(source_dir) / METADATA_FILE)
    price_records = _read_jsonl_gz(Path(source_dir) / PRICE_FILE)

    stats = {
        "metadata_rows": len(metadata_records),
        "metadata_matched": 0,
        "metadata_appended": 0,
        "metadata_candidate_duplicates": 0,
        "price_rows": len(price_records),
        "price_matched": 0,
        "price_appended": 0,
        "price_candidate_duplicates": 0,
        "price_reference_rows": sum(len(record.get("price_references") or []) for record in price_records),
    }

    by_name, spatial = _build_indexes(hotels)
    for hotel in hotels:
        hotel.setdefault("price_references", [])
    consumed_targets: set[str] = set()
    for record in metadata_records:
        _prepare_location(record, aliases)
        name_key = _normalize_name(record.get("name"))
        coordinates = _coordinates(record)
        named_candidates = by_name.get(name_key, []) if name_key else []
        nearby = _nearby_ids(coordinates, spatial, DUPLICATE_CANDIDATE_METERS)
        candidate_ids = sorted({str(item.get("hotel_id")) for item in named_candidates} | set(nearby))
        exact_geo = []
        if coordinates:
            for candidate in named_candidates:
                candidate_coordinates = _coordinates(candidate)
                if candidate_coordinates and _distance_m(coordinates, candidate_coordinates) <= METADATA_MATCH_METERS:
                    exact_geo.append(candidate)
        if len(exact_geo) == 1 and str(exact_geo[0].get("hotel_id")) not in consumed_targets:
            target = exact_geo[0]
            target_id = str(target.get("hotel_id"))
            _attach_source(target, record, "exact_name_and_coordinates", candidate_ids)
            consumed_targets.add(target_id)
            stats["metadata_matched"] += 1
        else:
            appended = _append_source_record(hotels, record, candidate_ids, used_ids)
            stats["metadata_appended"] += 1
            stats["metadata_candidate_duplicates"] += bool(candidate_ids)

            if name_key:
                by_name[name_key].append(appended)
            if coordinates:
                spatial[_grid_bucket(coordinates)].append(appended)



    price_key_counts: dict[tuple[str, str], int] = defaultdict(int)
    for record in price_records:
        _prepare_location(record, aliases)
        city = _price_source_city(record, aliases)
        name_key = _normalize_name(record.get("name"))
        if city and name_key:
            price_key_counts[(name_key, city.casefold())] += 1

    by_name, spatial = _build_indexes(hotels)
    for record in price_records:
        city = _price_source_city(record, aliases)
        name_key = _normalize_name(record.get("name"))
        named_candidates = by_name.get(name_key, []) if name_key else []
        city_candidates = [
            candidate for candidate in named_candidates
            if city and _normalize_city((candidate.get("location") or {}).get("city"), aliases) == city
        ]
        unique_source_key = bool(
            city and name_key and price_key_counts[(name_key, city.casefold())] == 1
        )
        target = city_candidates[0] if unique_source_key and len(city_candidates) == 1 else None
        candidate_ids = sorted(str(item.get("hotel_id")) for item in city_candidates)
        if target is not None:
            _attach_source(target, record, "exact_name_and_verified_city", candidate_ids)
            stats["price_matched"] += 1
        else:
            appended = _append_source_record(hotels, record, candidate_ids, used_ids)
            stats["price_appended"] += 1
            stats["price_candidate_duplicates"] += bool(candidate_ids)
            if name_key:
                by_name[name_key].append(appended)
            coordinates = _coordinates(record)
            if coordinates:
                spatial[_grid_bucket(coordinates)].append(appended)

    stats["total_hotels"] = len(hotels)
    log.info(
        "Hotel enrichment: metadata matched=%d appended=%d; price rows matched=%d appended=%d; total=%d",
        stats["metadata_matched"], stats["metadata_appended"],
        stats["price_matched"], stats["price_appended"], stats["total_hotels"],
    )
    return hotels, stats
