#!/usr/bin/env python3
"""Live smoke check for the registered RZD search_transport tool."""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agent.tools.executor import ToolExecutor
from backend.app.agent.tools.factory import build_registry
from backend.app.catalog.service import CatalogGateway


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-city", default="Москва")
    parser.add_argument("--to-city", default="Казань")
    parser.add_argument("--date", default=(date.today() + timedelta(days=7)).isoformat())
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    catalog = CatalogGateway()
    registry = build_registry(catalog, {"trip": {}})
    executed = await ToolExecutor(registry).execute("search_transport", {
        "from_city": args.from_city,
        "to_city": args.to_city,
        "type": "train",
        "date_from": args.date,
    })
    if not executed.get("ok"):
        print("tool_error=", executed.get("error"), executed.get("message"))
        return 1

    data = executed.get("data") or {}
    options = data.get("transport_options") or []
    print(f"route={args.from_city} -> {args.to_city} date={args.date}")
    print(f"outcome={data.get('outcome')} count={data.get('count')}")
    if options:
        first = options[0]
        print("first_train=", first.get("train_number"))
        print("departure_local=", first.get("departure_time_local"))
        print("arrival_local=", first.get("arrival_time_local"))
        print("price=", first.get("price"))
        print("availability=", first.get("availability"))
    for warning in data.get("warnings", []):
        print("warning=", warning)
    return 0 if data.get("outcome") in {"results", "no_results"} else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
