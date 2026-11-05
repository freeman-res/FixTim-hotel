"""Check the deployed catalog, estimates, climate and real BGE-M3 RAG index."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.catalog.service import get_catalog_gateway


async def main() -> int:
    errors: list[str] = []
    catalog_dir = ROOT / "data" / "catalog"
    for name in ("hotels.json", "destinations.json", "transport_options.json",
                 "hotel_price_estimates.json", "flight_route_price_estimates.json",
                 "climate.json"):
        path = catalog_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing or empty: {path.relative_to(ROOT)}")
        else:
            print(f"OK {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")

    gateway = get_catalog_gateway()
    status = await gateway.get_data_status()
    for source in ("hotels", "destinations", "transport", "climate"):
        info = status.get(source) or {}
        if not info.get("available"):
            errors.append(f"{source}: {info.get('reason') or 'unavailable'}")

    rag = await gateway.rag_status()
    print("RAG", json.dumps(rag, ensure_ascii=False))
    if not rag.get("available"):
        errors.append("RAG index unavailable")
    elif rag.get("model") != "bge-m3" or rag.get("dim") != 1024 or rag.get("chunks", 0) < 30000:
        errors.append("RAG index has unexpected model, dimension or hotel coverage")
    else:
        hits = await gateway.retrieve_descriptions("отель в Казани", top_k=3)
        print("RAG hits", [(hit.get("hotel_id"), hit.get("score")) for hit in hits])
        if not hits:
            errors.append("BGE-M3 query returned no hits from the runtime index")

    hotel_count = len(gateway.provider.load_hotels())
    indexed = rag.get("unique_hotels") or 0
    print(f"Hotel catalog: {hotel_count}; RAG unique hotels: {indexed}")
    if indexed < hotel_count:
        print(f"WARN: {hotel_count - indexed} catalog hotels are not represented in the existing RAG index")

    hotels = await gateway.find_offers({"city": "Казань"})
    if not hotels or not any(h.get("price_estimate") for h in hotels):
        errors.append("Kazan hotels or synthetic nightly prices unavailable")
    climate = await gateway.get_weather("Казань", month=11)
    if not climate or not climate.get("weather"):
        errors.append("Kazan November climate unavailable")

    for error in errors:
        print("FAIL", error)
    if errors:
        return 1
    print("PASS: catalog, estimates, climate and BGE-M3 RAG")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
