from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from backend.app.catalog.climate.service import ClimateService
from backend.app.catalog.providers.json import JsonProvider
from backend.app.catalog.service import CatalogGateway
from backend.app.catalog.destinations.service import DestinationsService


CLIMATE_ROW = {
    "destination_id": "dest_t_001", "month": 11,
    "temp_mean_c": 4.2, "precipitation_mean_mm_per_day": 1.8,
    "sample_days": 300, "period": "2016-2025",
    "kind": "historical_monthly_normal",
    "source": {"name": "Open-Meteo Historical Weather API", "type": "historical_reanalysis",
               "url": "https://archive-api.open-meteo.com/v1/archive",
               "retrieved_at": "2026-10-28T00:00:00+00:00"},
    "is_demo": False,
}


@pytest.fixture
def weather_provider(test_data_dir):
    (test_data_dir / "climate.json").write_text(
        json.dumps([CLIMATE_ROW], ensure_ascii=False), encoding="utf-8"
    )
    return JsonProvider(test_data_dir)


@pytest.mark.asyncio
async def test_gateway_reads_monthly_climate_data(weather_provider):
    gateway = CatalogGateway(provider=weather_provider)
    result = await gateway.get_climate("dest_t_001", 11)
    assert result["temp_mean_c"] == 4.2
    assert result["kind"] == "historical_monthly_normal"
    assert (await gateway.get_data_status())["climate"]["available"] is True


@pytest.mark.asyncio
async def test_gateway_resolves_city_and_falls_back_to_monthly_normal(weather_provider):
    gateway = CatalogGateway(provider=weather_provider)
    gateway.climate.today = lambda: date(2026, 10, 28)
    result = await gateway.get_weather("Калининград", target_date="2026-11-28")
    assert result["city"] == "Калининград"
    assert result["weather"]["type"] == "climate_estimate"
    assert result["weather"]["expected_temp_c"] == 4.2
    assert await gateway.get_weather("Несуществующий город") is None


@pytest.mark.asyncio
async def test_gateway_supports_expected_weather_contract(weather_provider):
    gateway = CatalogGateway(provider=weather_provider)
    gateway.climate.today = lambda: date(2026, 10, 28)
    result = await gateway.get_expected_weather("dest_t_001", 31)
    assert result["type"] == "climate_estimate"


def test_exact_weather_uses_requested_day_and_keeps_forecast_label(weather_provider):
    calls = []

    def responder(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.params["forecast_days"] == "3"
        return httpx.Response(200, json={"daily": {
            "time": ["2026-10-28", "2026-10-29", "2026-10-30"],
            "temperature_2m_min": [1.0, 2.0, 3.0],
            "temperature_2m_max": [5.0, 6.0, 7.0],
            "precipitation_sum": [0.0, 1.0, 2.0],
            "weather_code": [0, 3, 61],
        }})

    with httpx.Client(transport=httpx.MockTransport(responder)) as client:
        service = ClimateService(weather_provider, client=client,
                                 today=lambda: date(2026, 10, 28))
        result = service.get_expected_weather("dest_t_001", 2)
    assert len(calls) == 1
    assert result["type"] == "exact_forecast"
    assert result["target_date"] == "2026-10-30"
    assert result["forecast"]["temp_min_c"] == 3.0
    assert result["forecast"]["temp_max_c"] == 7.0
    assert result["forecast"]["precipitation_mm"] == 2.0


def test_far_date_is_historical_average_not_daily_forecast(weather_provider):
    def no_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError("far date must not call short-term forecast")

    with httpx.Client(transport=httpx.MockTransport(no_request)) as client:
        service = ClimateService(weather_provider, client=client,
                                 today=lambda: date(2026, 10, 28))
        result = service.get_expected_weather("dest_t_001", 31)
    assert result["type"] == "climate_estimate"
    assert result["target_date"] == "2026-11-28"
    assert result["expected_temp_c"] == 4.2
    assert result["source"]["name"] == "Open-Meteo Historical Weather API"
    assert result["note"] == "historical_monthly_average_not_forecast"


def test_day_six_uses_climate_instead_of_forecast(weather_provider):
    def no_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError("day six must not call forecast")

    with httpx.Client(transport=httpx.MockTransport(no_request)) as client:
        service = ClimateService(weather_provider, client=client,
                                 today=lambda: date(2026, 10, 28))
        result = service.get_expected_weather("dest_t_001", 6)
    assert result["type"] == "climate_estimate"


def test_forecast_api_failure_falls_back_to_labelled_climate(weather_provider):
    with httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(503))) as client:
        service = ClimateService(weather_provider, client=client,
                                 today=lambda: date(2026, 10, 28))
        result = service.get_expected_weather("dest_t_001", 4)
    assert result["target_date"] == "2026-11-01"
    assert result["type"] == "climate_estimate"
    assert result["note"] == "historical_monthly_average_not_forecast"


def test_destination_suggestion_includes_monthly_climate(weather_provider):
    service = DestinationsService(weather_provider)
    result = service.suggest_destinations({"travel_month": 11})
    kaliningrad = next(row for row in result if row["destination_id"] == "dest_t_001")
    assert kaliningrad["climate"]["temp_mean_c"] == 4.2
    assert kaliningrad["climate"]["kind"] == "historical_monthly_normal"


def test_import_aggregation_ignores_missing_days():
    from scripts.import_climate_normals import aggregate_normals

    payload = {"daily": {
        "time": ["2024-10-01", "2024-10-02", "2024-11-01"],
        "temperature_2m_mean": [10.0, None, 2.0],
        "precipitation_sum": [0.0, 4.0, 1.0],
    }}
    rows = aggregate_normals(payload)
    assert rows[10]["temp_mean_c"] == 10.0
    assert rows[10]["precipitation_mean_mm_per_day"] == 2.0
    assert rows[10]["sample_days"] == 1
    assert rows[11]["temp_mean_c"] == 2.0


def test_nasa_climatology_parses_monthly_temperature_and_precipitation():
    from scripts.import_climate_nasa import monthly_normals

    months = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG",
              "SEP", "OCT", "NOV", "DEC")
    payload = {"properties": {"parameter": {
        "T2M": {month: float(i) for i, month in enumerate(months, 1)},
        "PRECTOTCORR": {month: 2.5 for month in months},
    }}, "parameters": {"T2M": {"units": "C"}, "PRECTOTCORR": {"units": "mm/day"}}}
    rows = monthly_normals(payload)
    assert len(rows) == 12
    assert rows[11]["temp_mean_c"] == 11.0
    assert rows[11]["precipitation_mean_mm_per_day"] == 2.5
