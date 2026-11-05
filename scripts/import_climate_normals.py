"""Build data/catalog/climate.json from Open-Meteo historical daily data.

The rows are monthly historical averages, never date-specific forecasts.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DATA_DIR = ROOT / "data" / "catalog"


def aggregate_normals(payload: dict) -> dict[int, dict]:
    """Average daily temperatures and precipitation by calendar month."""
    daily = payload.get("daily") or {}
    dates = daily.get("time") or []
    temperatures = daily.get("temperature_2m_mean") or []
    precipitation = daily.get("precipitation_sum") or []
    accum = {month: {"temps": [], "rain": []} for month in range(1, 13)}
    for index, day_text in enumerate(dates):
        try:
            month = date.fromisoformat(day_text).month
        except (TypeError, ValueError):
            continue
        temp = temperatures[index] if index < len(temperatures) else None
        rain = precipitation[index] if index < len(precipitation) else None
        if isinstance(temp, (int, float)) and not isinstance(temp, bool) and math.isfinite(temp):
            accum[month]["temps"].append(float(temp))
        if isinstance(rain, (int, float)) and not isinstance(rain, bool) and math.isfinite(rain):
            accum[month]["rain"].append(float(rain))
    return {
        month: {
            "temp_mean_c": round(sum(values["temps"]) / len(values["temps"]), 1),
            "precipitation_mean_mm_per_day": (
                round(sum(values["rain"]) / len(values["rain"]), 1)
                if values["rain"] else None),
            "sample_days": len(values["temps"]),
        }
        for month, values in accum.items() if values["temps"]
    }


def _batch_response(client: httpx.Client, batch: list[dict], start_year: int,
                    end_year: int) -> list[dict]:
    latitudes = ",".join(str(d["location"]["latitude"]) for d in batch)
    longitudes = ",".join(str(d["location"]["longitude"]) for d in batch)
    params = {
        "latitude": latitudes, "longitude": longitudes,
        "start_date": f"{start_year}-01-01", "end_date": f"{end_year}-12-31",
        "daily": "temperature_2m_mean,precipitation_sum", "timezone": "auto",
    }
    for attempt in range(5):
        try:
            response = client.get(ARCHIVE_URL, params=params)
            response.raise_for_status()
            payload = response.json()
            rows = payload if isinstance(payload, list) else [payload]
            if len(rows) != len(batch):
                raise ValueError(f"Expected {len(batch)} locations, received {len(rows)}")
            return rows
        except (httpx.HTTPError, ValueError) as exc:
            if attempt == 4:
                raise RuntimeError(f"Historical API batch failed: {exc}") from exc
            retry_after = (exc.response.headers.get("Retry-After")
                           if isinstance(exc, httpx.HTTPStatusError) else None)
            delay = max(float(retry_after), 15 * (attempt + 1)) if retry_after and retry_after.isdigit() else 15 * (attempt + 1)
            time.sleep(delay)
    raise AssertionError("unreachable")


def build_climate(data_dir: Path = DATA_DIR, *, start_year: int = 2016,
                  end_year: int = 2025, limit: int | None = None,
                  batch_size: int = 10, pause_seconds: float = 12,
                  client: httpx.Client | None = None) -> dict:
    if start_year > end_year or end_year >= datetime.now().year:
        raise ValueError("Historical period must end before the current year")
    destinations = json.loads((data_dir / "destinations.json").read_text(encoding="utf-8"))
    destinations = [d for d in destinations if d.get("destination_id")
                    and isinstance((d.get("location") or {}).get("latitude"), (int, float))
                    and isinstance((d.get("location") or {}).get("longitude"), (int, float))]
    if limit is not None:
        destinations = destinations[:limit]
    if not destinations:
        raise ValueError("No destinations with coordinates")
    progress_file = data_dir / f".climate_progress_{start_year}_{end_year}.json"
    progress = json.loads(progress_file.read_text(encoding="utf-8")) if progress_file.exists() else {}
    rows = [row for destination in destinations
            for row in progress.get(destination["destination_id"], [])]
    fetched_at = datetime.now(timezone.utc).isoformat()
    owns_client = client is None
    client = client or httpx.Client(timeout=60)
    try:
        for start in range(0, len(destinations), batch_size):
            batch = destinations[start:start + batch_size]
            if all(len(progress.get(d["destination_id"], [])) == 12 for d in batch):
                print(f"Climate cached: {min(start + batch_size, len(destinations))}/{len(destinations)} cities", flush=True)
                continue
            if start and pause_seconds:
                time.sleep(pause_seconds)
            payloads = _batch_response(client, batch, start_year, end_year)
            for destination, payload in zip(batch, payloads):
                destination_rows = []
                for month, normal in aggregate_normals(payload).items():
                    destination_rows.append({
                        "destination_id": destination["destination_id"],
                        "month": month, **normal,
                        "kind": "historical_monthly_normal",
                        "period": f"{start_year}-{end_year}",
                        "source": {"name": "Open-Meteo Historical Weather API",
                                   "type": "historical_reanalysis", "url": ARCHIVE_URL,
                                   "retrieved_at": fetched_at,
                                   "data_as_of": f"{end_year}-12-31"},
                        "is_demo": False,
                    })
                progress[destination["destination_id"]] = destination_rows
                rows.extend(destination_rows)
            temporary = progress_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(progress, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            temporary.replace(progress_file)
            print(f"Climate: {min(start + batch_size, len(destinations))}/{len(destinations)} cities", flush=True)
    finally:
        if owns_client:
            client.close()
    covered = {row["destination_id"] for row in rows}
    if len(covered) != len(destinations) or len(rows) != 12 * len(destinations):
        raise RuntimeError(f"Climate incomplete: {len(covered)}/{len(destinations)} cities, {len(rows)} rows")
    rows.sort(key=lambda row: (row["destination_id"], row["month"]))
    output = data_dir / ("climate_sample.json" if limit is not None else "climate.json")
    output.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    progress_file.unlink(missing_ok=True)
    return {"cities": len(covered), "rows": len(rows), "period": f"{start_year}-{end_year}",
            "output": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--pause-seconds", type=float, default=12)
    args = parser.parse_args()
    print(json.dumps(build_climate(limit=args.limit, batch_size=args.batch_size,
                                   pause_seconds=args.pause_seconds), ensure_ascii=False))
