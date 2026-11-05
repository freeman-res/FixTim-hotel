"""End-to-end live source smoke, with clearly labelled fallback."""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.catalog.service import CatalogGateway
from backend.app.agent.tools.catalog_adapter import AgentCatalogAdapter
from backend.app.agent.tools.search_hotels import search_hotels
from backend.app.agent.tools.search_transport import search_transport
from backend.app.agent.schemas import SearchHotelsArgs, SearchFilters, SearchTransportArgs


async def main():
    gateway = CatalogGateway()
    cases = [
        ("flight", gateway.find_transport({"type": "plane", "from_city": "Москва", "to_city": "Казань", "date_from": "2026-11-18"})),
        ("hotel", gateway.find_offers({"city": "Казань", "check_in": "2026-11-18", "check_out": "2026-11-20", "guests": 2})),
    ]
    if os.getenv("TUTU_MCP_ENABLED", "true").lower() not in {"0", "false", "no"}:
        cases.insert(1, ("train", gateway.find_transport({"type": "train", "from_city": "Москва", "to_city": "Казань", "date_from": "2026-11-18"})))
    for label, coro in cases:
        try:
            rows = await coro
            first = rows[0] if rows else {}
            print(json.dumps({
                "kind": label, "count": len(rows),
                "first_id": first.get("transport_id") or first.get("hotel_id"),
                "source": (first.get("source") or {}).get("name"),
                "record_kind": first.get("record_kind"),
                "actual_price": first.get("price"),
                "price_estimate": first.get("price_estimate"),
            }, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"kind": label, "error": str(exc)}, ensure_ascii=False))
    adapter = AgentCatalogAdapter(gateway)
    state = {"trip": {"origin_city": "Москва", "city": "Казань", "check_in": "2026-11-18",
                      "check_out": "2026-11-20", "guests": 2, "adults": 1}}
    hotel_tool = await search_hotels(SearchHotelsArgs(filters=SearchFilters(city="Казань",
        check_in="2026-11-18", check_out="2026-11-20", guests=2)), adapter, state)
    flight_tool = await search_transport(SearchTransportArgs(type="plane", from_city="Москва",
        to_city="Казань", date_from="2026-11-18"), adapter, state)
    print(json.dumps({"kind": "agent_tools", "hotel_count": hotel_tool["count"],
        "flight_count": flight_tool["count"], "flight_outcome": flight_tool["outcome"],
        "hotel_warning": hotel_tool["warnings"], "flight_warning": flight_tool["warnings"]}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
