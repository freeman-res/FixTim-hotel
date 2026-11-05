"""Import NASA POWER observed/reanalysis monthly climatology for every catalog city."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "catalog"
API_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG",
          "SEP", "OCT", "NOV", "DEC")


def monthly_normals(payload: dict) -> dict[int, dict]:
    """Read NASA's monthly means, with explicit unit and missing-value checks."""
    units = payload.get("parameters") or {}
    if ((units.get("T2M") or {}).get("units") != "C"
            or (units.get("PRECTOTCORR") or {}).get("units") != "mm/day"):
        raise ValueError("Unexpected NASA POWER climate units")
    params = (payload.get("properties") or {}).get("parameter") or {}
    temps = params.get("T2M") or {}
    rain = params.get("PRECTOTCORR") or {}
    result = {}
    for month, code in enumerate(MONTHS, 1):
        temp, precip = temps.get(code), rain.get(code)
        if (not isinstance(temp, (int, float)) or isinstance(temp, bool)
                or not isinstance(precip, (int, float)) or isinstance(precip, bool)
                or not math.isfinite(temp) or not math.isfinite(precip)
                or temp <= -900 or precip < 0):
            raise ValueError(f"Missing NASA POWER value for {code}")
        result[month] = {"temp_mean_c": round(float(temp), 1),
                         "precipitation_mean_mm_per_day": round(float(precip), 2)}
    return result


async def fetch_city(client: httpx.AsyncClient, destination: dict) -> tuple[str, list[dict]]:
    did = destination["destination_id"]
    loc = destination["location"]
    params = {"parameters": "T2M,PRECTOTCORR", "community": "AG",
              "longitude": loc["longitude"], "latitude": loc["latitude"],
              "format": "JSON"}
    for attempt in range(4):
        try:
            response = await client.get(API_URL, params=params)
            response.raise_for_status()
            payload = response.json()
            normals = monthly_normals(payload)
            range_text = (payload.get("header") or {}).get("range", "")
            years = re.findall(r"\b\d{4}\b", range_text)
            if len(years) < 2:
                raise ValueError("NASA climatology period missing")
            period = f"{years[0]}-{years[-1]}"
            retrieved_at = datetime.now(timezone.utc).isoformat()
            return did, [{
                "destination_id": did, "month": month, **normal,
                "kind": "historical_monthly_normal", "period": period,
                "source": {"name": "NASA POWER Climatology API",
                           "type": "historical_reanalysis", "url": API_URL,
                           "retrieved_at": retrieved_at,
                           "data_as_of": f"{years[-1]}-12-31"},
                "is_demo": False,
            } for month, normal in normals.items()]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            if attempt == 3:
                raise RuntimeError(f"NASA climate failed for {did}: {exc}") from exc
            await asyncio.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


async def build_climate(data_dir: Path = DATA_DIR, *, concurrency: int = 4,
                        limit: int | None = None) -> dict:
    destinations = json.loads((data_dir / "destinations.json").read_text(encoding="utf-8"))
    destinations = [d for d in destinations if d.get("destination_id")
                    and isinstance((d.get("location") or {}).get("latitude"), (int, float))
                    and isinstance((d.get("location") or {}).get("longitude"), (int, float))]
    if limit is not None:
        destinations = destinations[:limit]
    if not destinations or concurrency < 1:
        raise ValueError("No destinations with coordinates or invalid concurrency")
    progress_file = data_dir / ".climate_nasa_progress.json"
    progress = json.loads(progress_file.read_text(encoding="utf-8")) if progress_file.exists() else {}
    async with httpx.AsyncClient(timeout=45) as client:
        pending = [d for d in destinations if len(progress.get(d["destination_id"], [])) != 12]
        for start in range(0, len(pending), concurrency):
            batch = pending[start:start + concurrency]
            outcomes = await asyncio.gather(*(fetch_city(client, d) for d in batch),
                                            return_exceptions=True)
            errors = []
            for outcome in outcomes:
                if isinstance(outcome, BaseException):
                    errors.append(outcome)
                else:
                    did, rows = outcome
                    progress[did] = rows
            temporary = progress_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(progress, ensure_ascii=False,
                                            separators=(",", ":")), encoding="utf-8")
            temporary.replace(progress_file)
            print(f"NASA climate: {len(progress)}/{len(destinations)} cities", flush=True)
            if errors:
                raise RuntimeError(f"{len(errors)} city requests failed; rerun to resume") from errors[0]
    rows = [row for d in destinations for row in progress.get(d["destination_id"], [])]
    if len(rows) != len(destinations) * 12:
        raise RuntimeError(f"Climate incomplete: {len(rows)} rows")
    rows.sort(key=lambda row: (row["destination_id"], row["month"]))
    output = data_dir / ("climate_sample.json" if limit is not None else "climate.json")
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(rows, ensure_ascii=False,
                                    separators=(",", ":")), encoding="utf-8")
    temporary.replace(output)
    progress_file.unlink(missing_ok=True)
    return {"cities": len(destinations), "rows": len(rows),
            "period": rows[0]["period"], "output": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(build_climate(concurrency=args.concurrency,
                                               limit=args.limit)), ensure_ascii=False))
