#!/usr/bin/env python3
"""Импорт сырых CSV-датасетов в нормализованные JSON для Catalog Service
Что импортируется:
    datasets/hotels-russia-for-agent.csv → data/catalog/hotels.json
    datasets/flights_ru.csv + buses_full.csv → data/catalog/transport_options.json
    datasets/cities.csv → data/catalog/destinations.json"""
from __future__ import annotations
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
PROJECT_ROOT   = Path(__file__).resolve().parent.parent
DATA_RAW       = Path(os.getenv("CATALOG_SOURCE_DIR", str(PROJECT_ROOT / "datasets")))
DATA_CATALOG   = Path(os.getenv("CATALOG_DATA_DIR", str(PROJECT_ROOT / "data" / "catalog")))
DATA_NORMALIZED = PROJECT_ROOT / "data" / "normalized"

IMPORT_RETRIEVED_AT = datetime.now(timezone.utc).isoformat()



_CITY_ALIASES: dict[str, str] = {}


def _load_city_aliases() -> None:
    global _CITY_ALIASES
    p = DATA_NORMALIZED / "city_aliases.json"
    if not p.exists():
        log.warning("city_aliases.json не найден — города не будут нормализованы. "
                    "Запусти scripts/build_city_aliases.py")
        return
    try:
        _CITY_ALIASES = json.loads(p.read_text(encoding="utf-8"))
        log.info("city_aliases: загружено %d алиасов", len(_CITY_ALIASES))
    except Exception as exc:
        log.error("Ошибка чтения city_aliases.json: %s", exc)

def _norm_city(name: str | None) -> str | None:
    """'Moscow' → 'Москва'. Неизвестное возвращаем как есть."""
    if not name:
        return None
    key = name.strip().lower()
    return _CITY_ALIASES.get(key, name.strip())



HOTELS_CSV = DATA_RAW / "hotels-russia-for-agent.csv"
FLIGHTS_CSV = DATA_RAW / "flights_ru.csv"
BUSES_CSV  = DATA_RAW / "buses_full.csv"
CITIES_CSV = DATA_RAW / "cities.csv"
HOTEL_ENRICHMENT_DIR = DATA_RAW / "hotel_enrichment"
HOTEL_ENRICHMENT_FILES = (
    "booking_hotels_ru.jsonl.gz",
    "hotel_price_references.jsonl.gz",
)


def validate_hotel_enrichment_sources(source_dir: Path) -> bool:
    """Allow enrichment to be absent, but reject incomplete prepared inputs."""
    source_dir = Path(source_dir)
    if not source_dir.exists():
        return False
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Hotel enrichment path is not a directory: {source_dir}")
    missing = [name for name in HOTEL_ENRICHMENT_FILES if not (source_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(
            "Incomplete hotel enrichment directory; missing prepared source file(s): "
            + ", ".join(missing)
        )
    return True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("import_data")



def clean_str(value: Any) -> str | None:
    """Trim + схлопывание пробелов. NaN/пусто/literal-'nan' → None."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null", "n/a", "na", "-"}:
        return None
    return re.sub(r"\s+", " ", s)
def clean_float(value: Any) -> float | None:
    """Мусор и NaN → None. Не бросаем, чтобы не падать на одной строке."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f
def clean_int(value: Any) -> int | None:
    f = clean_float(value)
    if f is None:
        return None
    return int(round(f))
def clean_bool(value: Any) -> bool | None:
    """True/False из bool, 'true'/'false', 1/0, 'да'/'нет'. Иначе None (≠ False!)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"true", "1", "yes", "y", "да"}:
        return True
    if s in {"false", "0", "no", "n", "нет"}:
        return False
    return None
def slugify(text: str | None) -> str:
    """
    Простой ASCII-slug для ID. Кириллица транслитерируется вручную —
    нужно для человекочитаемых ID вида 'transport_bus_abakan_bograd_1530'.
    """
    if not text:
        return "unknown"
    table = str.maketrans({
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    })
    s = text.strip().lower().translate(table)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "unknown"


def load_csv(path: Path) -> pd.DataFrame | None:
    """
    Отсутствие/битый файл → log + None (а не exception).
    dtype=str гарантирует, что pandas не превратит 'stars' в float и не
    вставит 1.0 вместо 1. NaN остаются настоящими NaN — clean_* их разберут.
    """
    if not path.exists():
        log.warning("Файл не найден, пропускаю: %s", path)
        return None
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=True, low_memory=False)
        log.info("Загружено %s (%d строк × %d колонок)", path.name, len(df), len(df.columns))
        return df
    except Exception as exc:
        log.error("Не удалось прочитать %s: %s", path, exc)
        return None
def write_json(path: Path, records: list[dict]) -> None:
    """
    Атомарная запись (tmp + replace) — при падении посреди записи
    старый файл останется целым. ensure_ascii=False — кириллица читаема.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    tmp.replace(path)
    log.info("Записан %s (%d записей)", path.relative_to(PROJECT_ROOT), len(records))







def import_hotels() -> tuple[list[dict], int]:
    """
    Отели из hotels-russia.csv (OSM + QC-версия v2, 41 колонка).
    Критичные поля: name, latitude, longitude.
    Приоритет источника для city:
        city_final > city_verified > city
    Приоритет для ID:
        hotel_key > osm_id > row_index
    Приоритет для RAG-текста:
        city_agent_search_text > search_text_verified > search_text
    """
    df = load_csv(HOTELS_CSV)
    if df is None:
        return [], 0

    hotels: list[dict] = []
    dropped = 0

    for idx, row in df.iterrows():
        name = clean_str(row.get("name"))
        lat  = clean_float(row.get("latitude"))
        lon  = clean_float(row.get("longitude"))

        if not name or lat is None or lon is None:
            dropped += 1
            continue


        hotel_key = clean_str(row.get("hotel_key"))
        osm_id    = clean_int(row.get("osm_id"))
        if hotel_key:
            hotel_id = hotel_key
        elif osm_id is not None:
            hotel_id = f"hotel_osm_{osm_id}"
        else:
            hotel_id = f"hotel_rf_{idx:05d}"


        city_final = (
            clean_str(row.get("city_final"))
            or clean_str(row.get("city_verified"))
            or clean_str(row.get("city"))
        )


        search_text = (
            clean_str(row.get("city_agent_search_text"))
            or clean_str(row.get("search_text_verified"))
            or clean_str(row.get("search_text"))
        )


        city_confidence = clean_str(row.get("city_final_confidence"))
        city_method     = clean_str(row.get("city_final_method"))
        city_qa_status  = clean_str(row.get("city_qa_status"))


        dup_count = clean_int(row.get("possible_duplicate_count"))

        hotels.append({
            "hotel_id": hotel_id,
            "name": name,
            "type": clean_str(row.get("type")),
            "location": {
                "latitude": lat,
                "longitude": lon,
                "city": city_final,
                "address": clean_str(row.get("address")),

                "city_confidence": city_confidence,
                "city_method": city_method,
                "city_qa_status": city_qa_status,
            },
            "stars": clean_int(row.get("stars")),
            "contacts": {
                "website": clean_str(row.get("website")),
                "phone": clean_str(row.get("phone")),
            },
            "amenities": {
                "internet": clean_str(row.get("internet")),
                "parking": clean_bool(row.get("parking")),
            },

            "search_text": search_text,

            "tags_json": clean_str(row.get("tags_json")),

            "possible_duplicate_count": dup_count,
            "price": None,
            "availability": {
                "status": "unknown",
                "note": "osm_poi_availability_not_tracked",
            },
            "source": {
                "name": "OpenStreetMap hotels-russia extract (QC v2)",
                "type": "public_api",
                "format": "dataset",
                "file": HOTELS_CSV.name,
                "url": "https://www.openstreetmap.org/",
                "retrieved_at": IMPORT_RETRIEVED_AT,
                "data_as_of": None,
            },
            "is_demo": False,
        })

    return hotels, dropped






def import_flights() -> tuple[list[dict], int]:
    df = load_csv(FLIGHTS_CSV)
    if df is None:
        return [], 0
    records: list[dict] = []
    dropped = 0
    seen_ids: set[str] = set()
    for idx, row in df.iterrows():
        origin_city = clean_str(row.get("origin_city"))
        dest_city   = clean_str(row.get("destination_city"))
        departure   = clean_str(row.get("departure_utc"))
        if not origin_city or not dest_city or not departure:
            dropped += 1
            continue
        callsign = clean_str(row.get("callsign")) or f"row{idx}"
        o_iata = (clean_str(row.get("origin_iata")) or "xxx").upper()
        d_iata = (clean_str(row.get("destination_iata")) or "xxx").upper()

        date_part = departure[:10].replace("-", "") if len(departure) >= 10 else "na"
        transport_id = f"transport_plane_{callsign}_{date_part}_{o_iata}_{d_iata}"

        if transport_id in seen_ids:
            transport_id = f"{transport_id}_{idx}"
        seen_ids.add(transport_id)
        records.append({
            "transport_id": transport_id,
            "type": "plane",
            "from": {
                "city": _norm_city(origin_city),
                "airport_name": clean_str(row.get("origin_airport")),
                "iata": None if o_iata == "XXX" else o_iata,
                "icao": clean_str(row.get("origin_icao")),

                "ambiguous": clean_bool(row.get("airport_ambiguous")),
                "candidates": clean_str(row.get("origin_candidates")),},
            "to": {
                "city": _norm_city(dest_city),
                "airport_name": clean_str(row.get("destination_airport")),
                "iata": None if d_iata == "XXX" else d_iata,
                "icao": clean_str(row.get("destination_icao")),
                "ambiguous": clean_bool(row.get("airport_ambiguous")),
                "candidates": clean_str(row.get("destination_candidates")), },
            "departure_utc": departure,
            "arrival_utc": clean_str(row.get("arrival_utc")),
            "duration_minutes": clean_int(row.get("duration_minutes")),
            "airline_icao": clean_str(row.get("airline_icao")),
            "callsign": callsign,

            "price": None,
            "price_note": "price_not_in_source_adsb_dataset",
            "availability": {
                "status": "unknown",
                "note": "historical_adsb_schedule_not_live_availability", },
            "source": {
                "name": clean_str(row.get("source")) or "flights_ru",
                "type": "public_api",
                "format": "dataset",
                "file": FLIGHTS_CSV.name,
                "url": None,
                "retrieved_at": IMPORT_RETRIEVED_AT,

                "data_as_of": "2026-Q3", },  "is_demo": False,})
    return records, dropped







def import_buses() -> tuple[list[dict], int]:
    """
    Автобусы из buses_full.csv
    КРИТИЧНО: trip_id в этом файле НЕ уникален — один trip_id может
    встречаться для forward/reverse и для разных departure_time_local.
    Фикс:
      transport_id = f"bus_{trip_id}_{direction}_{dep_slug}" — составной ключ.
      drop_duplicates по (trip_id, direction, departure_time_local) —
       Города нормализуются через _norm_city .
    """
    df = load_csv(BUSES_CSV)
    if df is None:
        return [], 0

    before = len(df)
    df = df.drop_duplicates(
        subset=["trip_id", "direction", "departure_time_local"],
        keep="first",  )
    deduped = before - len(df)
    if deduped:
        log.info("buses: удалено %d дублей по (trip_id, direction, departure_time)",
                 deduped)

    records: list[dict] = []
    dropped = 0
    seen_ids: set[str] = set()

    for idx, row in df.iterrows():
        trip_id   = clean_str(row.get("trip_id"))
        from_city = clean_str(row.get("from_city"))
        to_city   = clean_str(row.get("to_city"))

        if not trip_id or not from_city or not to_city:
            dropped += 1
            continue
        direction = clean_str(row.get("direction")) or "na"
        dep_time  = clean_str(row.get("departure_time_local")) or "na"
        dep_slug  = dep_time.replace(":", "")




        direction = clean_str(row.get("direction")) or "na"
        dep_time  = clean_str(row.get("departure_time_local")) or "na"
        dep_slug  = dep_time.replace(":", "")
        transport_id = f"transport_bus_{trip_id}_{direction}_{dep_slug}"
        if transport_id in seen_ids:
            transport_id = f"{transport_id}_{idx}"
        seen_ids.add(transport_id)

        price_from = clean_int(row.get("price_from_rub"))
        price_to   = clean_int(row.get("price_to_rub"))
        price_scope = clean_str(row.get("price_scope")) or "unspecified"

        dep_confirmed   = clean_bool(row.get("departure_date_confirmed"))
        arr_confirmed   = clean_bool(row.get("arrival_date_confirmed"))
        avail_confirmed = clean_bool(row.get("availability_confirmed"))

        if avail_confirmed is True:
            status = "confirmed"
        elif dep_confirmed is True or arr_confirmed is True:
            status = "partial"
        else:
            status = "unconfirmed"

        records.append({
            "transport_id": transport_id,
            "type": "bus",
            "original_trip_id": trip_id,
            "route_id": clean_str(row.get("route_id")),
            "direction": direction,
            "from": {
                "city": _norm_city(from_city),
                "station": clean_str(row.get("from_station")),
            },
            "to": {
                "city": _norm_city(to_city),
                "station": clean_str(row.get("to_station")),
            },
            "departure_time_local": dep_time,
            "arrival_time_local_unverified": clean_str(
                row.get("arrival_time_local_unverified_day")
            ),
            "duration_minutes": clean_int(row.get("duration_min")),
            "service_days_rule": clean_str(row.get("service_days_rule")),
            "service_period_raw": clean_str(row.get("service_period_raw")),
            "distance_km": clean_float(row.get("distance_km")),
            "carriers": clean_str(row.get("operator_or_carriers")),
            "price": {
                "amount_min_rub": price_from,
                "amount_max_rub": price_to,
                "currency": "RUB",
                "unit": "per_person",
                "scope": price_scope,
            } if (price_from is not None or price_to is not None) else None,
            "availability": {
                "status": status,
                "departure_date_confirmed": dep_confirmed,
                "arrival_date_confirmed": arr_confirmed,
                "availability_confirmed": avail_confirmed,
                "note": "route_level_snapshot_not_per_date_availability",
            },
            "source": {
                "name": clean_str(row.get("source")) or "buses_registry",
                "type": "public_api",
                "format": "dataset",
                "file": BUSES_CSV.name,
                "url": clean_str(row.get("source_url")),
                "retrieved_at": IMPORT_RETRIEVED_AT,
                "data_as_of": clean_str(row.get("snapshot_date")),
                "data_quality_notes": clean_str(row.get("data_quality_notes")),
            },
            "is_demo": False,
        })

    return records, dropped







def import_destinations() -> tuple[list[dict], int]:
    df = load_csv(CITIES_CSV)
    if df is None:
        return [], 0
    records: list[dict] = []
    dropped = 0
    seen_ids: set[str] = set()
    for idx, row in df.iterrows():
        city = clean_str(row.get("city"))
        lat  = clean_float(row.get("latitude"))
        lon  = clean_float(row.get("longitude"))
        if not city or lat is None or lon is None:
            dropped += 1
            continue


        oktmo_str = clean_str(row.get("oktmo"))
        dest_id = f"dest_oktmo_{oktmo_str}" if oktmo_str else f"dest_{slugify(city)}"
        if dest_id in seen_ids:
            dest_id = f"{dest_id}_{idx}"
        seen_ids.add(dest_id)

        records.append({
            "destination_id": dest_id,
            "name": city,
            "region": clean_str(row.get("region")),
            "oktmo": oktmo_str,
            "location": {"latitude": lat, "longitude": lon},
            "population": clean_int(row.get("population_2021")),


            "climate": None,
            "estimated_budget": None,
            "source": {
                "name": "russia_cities_reference",
                "type": "public_api",
                "format": "dataset",
                "file": CITIES_CSV.name,
                "url": None,
                "retrieved_at": IMPORT_RETRIEVED_AT,
                "data_as_of": "2021",       },
            "is_demo": False,
        })

    return records, dropped



def build_manifest(stats: dict[str, dict]) -> list[dict]:
    hotel_stats = stats.get("hotels", {})
    hotel_quality = hotel_stats.get("quality", {})
    hotel_rows = int(hotel_stats.get("rows_imported", 0))
    transport_quality = stats.get("transport_options", {}).get("quality", {})

    def missing_summary(label: str, key: str) -> str:
        count = int(hotel_quality.get(key, 0))
        pct = (100 * count / hotel_rows) if hotel_rows else 0.0
        return f"hotels: {label} missing {count}/{hotel_rows} ({pct:.1f}%)"

    bus_scopes = transport_quality.get("bus_price_scope_counts", {})
    bus_scope_summary = ", ".join(
        f"{name}={count}" for name, count in sorted(bus_scopes.items())
    ) or "none"
    manifest = {
        "generated_at": IMPORT_RETRIEVED_AT,
        "sources_imported": stats,
        "sources_missing": [
            {
                "expected_file": "reviews.json",
                "reason": "no review source dataset provided",
                "impact": "RAG retrieve_reviews will fall back to no results; "
                          "RAG over hotel search_text still works",
            },
            {
                "expected_file": "climate.json",
                "reason": "no climate/weather source dataset provided",
                "impact": "get_climate will return None",
            },
            {
                "expected_file": "transfer_options.json",
                "reason": "no transfer source dataset provided",
                "impact": "find_transfers will return []",
            },
            {
                "expected_file": "train_options.json",
                "reason": "no static railway dataset provided",
                "impact": "dated route searches use the online RZD provider; offline train data is unavailable",
            },
            {
                "expected_file": "offers.json",
                "reason": "no bookable offers/prices dataset provided",
                "impact": "hotels have price=null; archived price_references are not live offers and are not used for budgets",
            },
        ],
        "known_limitations": [
            "hotels: osm_id missing in 100% rows; hotel_id generated from row index",
            missing_summary("city", "rows_missing_city"),
            missing_summary("stars", "rows_missing_stars"),
            missing_summary("price", "rows_missing_price"),
            f"hotel price references: {hotel_stats.get('price_reference_rows', 0)} observations have unknown currency/date/occupancy and are not bookable prices",
            f"hotel enrichment: matched metadata={hotel_stats.get('enrichment', {}).get('metadata_matched', 0)}, added metadata={hotel_stats.get('enrichment', {}).get('metadata_appended', 0)}, matched price rows={hotel_stats.get('enrichment', {}).get('price_matched', 0)}, added price rows={hotel_stats.get('enrichment', {}).get('price_appended', 0)}",
            f"flights: prices missing {transport_quality.get('plane_rows_missing_price', 0)} rows; unknown is stored as null",
            "flights: departure/arrival in UTC; timezone per city not provided",
            f"buses: price scopes are not live per-departure fares ({bus_scope_summary})",
            f"buses: availability unconfirmed for {transport_quality.get('bus_rows_unconfirmed', 0)} rows",
            f"buses: destination station missing for {transport_quality.get('bus_rows_missing_to_station', 0)} rows",
            f"buses: {transport_quality.get('bus_rows_dropped_missing_route_fields', 0)} source rows omitted for missing route identifiers/cities",
            "destinations: no climate, seasonality or budget in cities.csv",
            f"cross-source: city aliases available={len(_CITY_ALIASES)}; unknown aliases remain unmatched",
        ],
    }
    return [manifest]


def main() -> None:
    for output_dir in (DATA_CATALOG, DATA_NORMALIZED):
        output_dir.mkdir(parents=True, exist_ok=True)
    log.info("=== Импорт данных в каталог ===")
    _load_city_aliases()
    log.info("Raw:  %s", DATA_RAW)
    log.info("Catalog output: %s", DATA_CATALOG)

    stats: dict[str, dict] = {}


    hotels, dropped = import_hotels()
    base_hotel_rows = len(hotels)
    enrichment_stats: dict[str, int] = {}
    if validate_hotel_enrichment_sources(HOTEL_ENRICHMENT_DIR):
        if __package__:
            from scripts.hotel_enrichment import load_prepared_hotel_sources
        else:
            from hotel_enrichment import load_prepared_hotel_sources

        hotels, enrichment_stats = load_prepared_hotel_sources(
            hotels, HOTEL_ENRICHMENT_DIR, city_aliases=_CITY_ALIASES
        )
    else:
        log.info("Prepared hotel enrichment not found at %s", HOTEL_ENRICHMENT_DIR)
    write_json(DATA_CATALOG / "hotels.json", hotels)
    stats["hotels"] = {
        "file": HOTELS_CSV.name,
        "rows_imported": len(hotels),
        "base_rows_imported": base_hotel_rows,
        "rows_dropped": dropped,
        "enrichment": enrichment_stats,
        "price_reference_rows": sum(len(h.get("price_references") or []) for h in hotels),
        "quality": {
            "rows_missing_city": sum(not (h.get("location") or {}).get("city") for h in hotels),
            "rows_missing_stars": sum(h.get("stars") is None for h in hotels),
            "rows_missing_price": sum(h.get("price") is None for h in hotels),
        },
        "output": str(DATA_CATALOG / "hotels.json"),
    }


    destinations, dropped = import_destinations()
    write_json(DATA_CATALOG / "destinations.json", destinations)
    stats["destinations"] = {
        "file": CITIES_CSV.name,
        "rows_imported": len(destinations),
        "rows_dropped": dropped,
        "output": str(DATA_CATALOG / "destinations.json"),
    }



    planes, dropped_p = import_flights()
    buses,  dropped_b = import_buses()
    transport = planes + buses
    write_json(DATA_CATALOG / "transport_options.json", transport)
    stats["transport_options"] = {
        "files": [FLIGHTS_CSV.name, BUSES_CSV.name],
        "rows_imported": len(transport),
        "rows_dropped": dropped_p + dropped_b,
        "quality": {
            "plane_rows_missing_price": sum(t.get("price") is None for t in planes),
            "bus_rows_unconfirmed": sum(
                (t.get("availability") or {}).get("status") != "confirmed" for t in buses
            ),
            "bus_rows_missing_to_station": sum(not (t.get("to") or {}).get("station") for t in buses),
            "bus_rows_dropped_missing_route_fields": dropped_b,
            "bus_price_scope_counts": {
                scope: sum(((t.get("price") or {}).get("scope") or "unknown") == scope for t in buses)
                for scope in sorted({(t.get("price") or {}).get("scope") or "unknown" for t in buses})
            },
        },
        "breakdown": {
            "plane": len(planes),
            "bus": len(buses),
            "train": 0,
        },
        "output": str(DATA_CATALOG / "transport_options.json"),
    }


    write_json(DATA_CATALOG / "_manifest.json", build_manifest(stats))


    print()
    print("=" * 68)
    print("СТАТИСТИКА ИМПОРТА")
    print("=" * 68)
    for name, s in stats.items():
        extra = ""
        if "breakdown" in s:
            b = s["breakdown"]
            extra = f"  (plane: {b['plane']}, bus: {b['bus']}, train: {b['train']})"
        print(f"  {name:<20} импортировано: {s['rows_imported']:>6}   "
              f"отброшено: {s['rows_dropped']:>5}{extra}")
    total_ok  = sum(s["rows_imported"] for s in stats.values())
    total_bad = sum(s["rows_dropped"]  for s in stats.values())
    print("-" * 68)
    print(f"  ИТОГО: импортировано {total_ok}, отброшено {total_bad} битых строк")
    print()
    print("НЕ импортировано (нет источника — зафиксировано в _manifest.json):")
    print("  - reviews.json           - нет файла с отзывами")
    print("  - climate.json           - нет файла климата/погоды")
    print("  - transfer_options.json  - нет файла трансферов")
    print("  - train_options.json     - нет ЖД-файла")
    print("  - offers.json            - нет продажных цен")
    print("=" * 68)


if __name__ == "__main__":
    main()
