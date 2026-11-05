"""Server readiness matrix for hotel prices and every supported transport kind."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.catalog.service import CatalogGateway


def price_of(record: dict) -> tuple[float | None, str]:
    price = record.get("price") or {}
    if isinstance(price, dict):
        amount = price.get("amount_min_rub") or price.get("total_amount")
        if isinstance(amount, (int, float)) and amount > 0:
            return amount, "source_price"
    amount = record.get("total_price")
    if isinstance(amount, (int, float)) and amount > 0:
        return amount, "source_price"
    estimate = record.get("price_estimate") or {}
    amount = estimate.get("amount_rub")
    if isinstance(amount, (int, float)) and amount > 0:
        return amount, "estimate"
    return None, "missing"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=(date.today() + timedelta(days=21)).isoformat())
    parser.add_argument("--skip-train", action="store_true", help="Local offline check only")
    args = parser.parse_args()
    check_in = date.fromisoformat(args.date)
    check_out = (check_in + timedelta(days=2)).isoformat()
    gateway = CatalogGateway()
    errors: list[str] = []

    cases = [
        ("hotels", gateway.find_offers({"city": "Казань", "check_in": args.date,
                                         "check_out": check_out, "adults": 1})),
        ("plane", gateway.find_transport({"type": "plane", "from_city": "Москва",
                                           "to_city": "Казань", "date_from": args.date,
                                           "adults": 1})),
        ("bus", gateway.find_transport({"type": "bus", "from_city": "Москва",
                                         "to_city": "Казань"})),
    ]
    if not args.skip_train:
        cases.append(("train", gateway.find_transport({"type": "train", "from_city": "Москва",
                                                         "to_city": "Казань", "date_from": args.date,
                                                         "adults": 1})))
    for kind, coroutine in cases:
        try:
            rows = await coroutine
            priced = [(row, *price_of(row)) for row in rows]
            priced = [entry for entry in priced if entry[1] is not None]
            first = priced[0] if priced else None
            report = {"kind": kind, "count": len(rows), "priced_count": len(priced),
                      "record_kind": (first[0].get("record_kind") if first else None),
                      "price_kind": ("snapshot_reference" if kind == "bus" and first else
                                     first[2] if first else None),
                      "amount": (first[1] if first else None),
                      "source": ((first[0].get("source") or {}).get("name") if first else None)}
            print(json.dumps(report, ensure_ascii=False), flush=True)
            if not rows or not priced:
                errors.append(f"{kind}: no priced result")
            elif kind == "plane" and first[0].get("record_kind") not in {"live_offer", "route_price_estimate"}:
                errors.append("plane: unexpected source kind")
            elif kind == "train" and first[0].get("record_kind") != "live_offer":
                errors.append("train: no dated live train offer")
        except Exception as exc:
            print(json.dumps({"kind": kind, "error": str(exc)}, ensure_ascii=False), flush=True)
            errors.append(f"{kind}: {type(exc).__name__}")

    for error in errors:
        print("FAIL", error)
    if errors:
        return 1
    print("PASS: hotel prices, plane, bus" + (" and train" if not args.skip_train else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
