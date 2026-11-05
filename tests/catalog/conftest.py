"""
tests/catalog/conftest.py
=========================
Общие фикстуры для тестов каталога.

Принципы:
    1. Никакого I/O в data/demo/ — фикстуры пишутся в tmp_path.
    2. Каждый тест получает СВЕЖИЙ CatalogGateway — никаких singleton-загрязнений.
    3. Отсутствующие файлы (transfers/climate/reviews) НЕ создаём —
       тесты должны проверять именно сценарий «источника нет».
    4. Никакой сети и никаких BGE-M3 — тесты должны проходить за секунды.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest



PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.catalog.providers.json import JsonProvider
from backend.app.catalog.service import CatalogGateway










@pytest.fixture
def sample_hotels() -> list[dict]:
    return [
        {
            "hotel_id": "hotel_t_001",
            "name": "Alpine Resort",
            "type": "hotel",
            "location": {"latitude": 55.7, "longitude": 37.6,
                         "city": "Москва", "address": "ул. Тверская 1"},
            "stars": 4,
            "contacts": {"website": None, "phone": None},
            "amenities": {"internet": "wlan", "parking": True},
            "search_text": "Alpine Resort hotel Москва",
            "price": {"amount_min_rub": 8000, "amount_max_rub": 12000,
                      "currency": "RUB", "unit": "per_night",
                      "scope": "per_departure"},
            "availability": {"status": "unknown", "note": "test"},
            "source": {"name": "test", "type": "demo", "format": "dataset",
                       "file": "test.csv", "url": None,
                       "retrieved_at": "2026-01-01T00:00:00Z",
                       "data_as_of": None},
            "is_demo": True,
        },
        {
            "hotel_id": "hotel_t_002",
            "name": "Budget Stay",
            "type": "hostel",
            "location": {"latitude": 55.75, "longitude": 37.62,
                         "city": "Москва", "address": None},
            "stars": 2,
            "contacts": {"website": None, "phone": None},
            "amenities": {"internet": "no", "parking": False},
            "search_text": "Budget Stay hostel Москва",
            "price": {"amount_min_rub": 1500, "amount_max_rub": 2500,
                      "currency": "RUB", "unit": "per_night",
                      "scope": "per_departure"},
            "availability": {"status": "unknown", "note": "test"},
            "source": {"name": "test", "type": "demo", "format": "dataset",
                       "file": "test.csv", "url": None,
                       "retrieved_at": "2026-01-01T00:00:00Z",
                       "data_as_of": None},
            "is_demo": True,
        },
        {


            "hotel_id": "hotel_t_003",
            "name": "No Stars Guesthouse",
            "type": "guest_house",
            "location": {"latitude": 59.9, "longitude": 30.3,
                         "city": "Санкт-Петербург", "address": None},
            "stars": None,
            "contacts": {"website": None, "phone": None},
            "amenities": {"internet": None, "parking": None},
            "search_text": "No Stars Guesthouse Санкт-Петербург",
            "price": None,
            "availability": {"status": "unknown", "note": "test"},
            "source": {"name": "test", "type": "demo", "format": "dataset",
                       "file": "test.csv", "url": None,
                       "retrieved_at": "2026-01-01T00:00:00Z",
                       "data_as_of": None},
            "is_demo": True,
        },
    ]


@pytest.fixture
def sample_transport() -> list[dict]:
    return [
        {

            "transport_id": "transport_plane_TEST1",
            "type": "plane",
            "from": {"city": "Москва", "airport_name": "SVO",
                     "iata": "SVO", "icao": "UUEE"},
            "to": {"city": "Калининград", "airport_name": "KGD",
                   "iata": "KGD", "icao": "UMKK"},
            "departure_utc": "2026-11-15T08:00:00+00:00",
            "arrival_utc": "2026-11-15T10:00:00+00:00",
            "duration_minutes": 120,
            "price": None,
            "availability": {"status": "unknown", "note": "test"},
            "source": {"name": "test", "type": "demo", "format": "dataset",
                       "file": "test.csv", "url": None,
                       "retrieved_at": "2026-01-01T00:00:00Z",
                       "data_as_of": None},
            "is_demo": True,
        },
        {

            "transport_id": "transport_bus_TEST2",
            "type": "bus",
            "from": {"city": "Москва", "station": "Автовокзал"},
            "to": {"city": "Тула", "station": None},
            "departure_time_local": "10:00",
            "schedule_date": "2026-11-15",
            "price": {"amount_min_rub": 600, "amount_max_rub": 800,
                      "currency": "RUB", "unit": "per_person",
                      "scope": "route_level_range_NOT_per_departure"},
            "availability": {"status": "unconfirmed", "note": "test"},
            "source": {"name": "test", "type": "demo", "format": "dataset",
                       "file": "test.csv", "url": None,
                       "retrieved_at": "2026-01-01T00:00:00Z",
                       "data_as_of": None},
            "is_demo": True,
        },
    ]


@pytest.fixture
def sample_destinations() -> list[dict]:
    return [
        {
            "destination_id": "dest_t_001",
            "name": "Калининград",
            "region": "Калининградская область",
            "oktmo": "27000000000",
            "location": {"latitude": 54.7, "longitude": 20.5},
            "population": 489359,
            "climate": None,
            "estimated_budget": None,
            "source": {"name": "test", "type": "demo", "format": "dataset",
                       "file": "test.csv", "url": None,
                       "retrieved_at": "2026-01-01T00:00:00Z",
                       "data_as_of": None},
            "is_demo": True,
        },
        {
            "destination_id": "dest_t_002",
            "name": "Тула",
            "region": "Тульская область",
            "oktmo": "70701000001",
            "location": {"latitude": 54.2, "longitude": 37.6},
            "population": 473622,
            "climate": None,
            "estimated_budget": None,
            "source": {"name": "test", "type": "demo", "format": "dataset",
                       "file": "test.csv", "url": None,
                       "retrieved_at": "2026-01-01T00:00:00Z",
                       "data_as_of": None},
            "is_demo": True,
        },
    ]


@pytest.fixture
def test_data_dir(tmp_path, sample_hotels, sample_transport, sample_destinations):
    """
    Записывает фикстуры в tmp_path. Отсутствующие файлы
    (transfer_options.json, climate.json, reviews.json) НЕ создаём —
    тесты должны проверять именно сценарий «источника нет».
    """
    (tmp_path / "hotels.json").write_text(
        json.dumps(sample_hotels, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "transport_options.json").write_text(
        json.dumps(sample_transport, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "destinations.json").write_text(
        json.dumps(sample_destinations, ensure_ascii=False), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def gateway(test_data_dir):
    """
    Свежий CatalogGateway на каждый тест. НЕ использует singleton
    get_catalog_gateway() — чтобы тесты не залипали на кэше друг друга.
    """
    return CatalogGateway(provider=JsonProvider(test_data_dir))