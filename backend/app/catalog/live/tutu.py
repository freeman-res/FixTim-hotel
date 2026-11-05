"""Read-only client for Tutu's public Streamable HTTP MCP endpoint."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import timedelta

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_TUTU_URL = "https://mcp.tutu.ru/mcp"


class TutuMcpClient:
    def __init__(self, url: str | None = None, timeout_seconds: float | None = None):
        self.url = url or os.getenv("TUTU_MCP_URL", DEFAULT_TUTU_URL)
        self.timeout_seconds = timeout_seconds or float(os.getenv("TUTU_MCP_TIMEOUT", "20"))
        if not self.url.startswith("https://"):
            raise ValueError("TUTU_MCP_URL must use HTTPS")

    async def _call(self, name: str, args: dict) -> dict:
        async with streamable_http_client(self.url) as (read, write, _):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=self.timeout_seconds)) as session:
                await session.initialize()
                result = await session.call_tool(name, args)
                if result.isError:
                    raise RuntimeError(f"Tutu MCP {name} returned an error")
                if isinstance(result.structuredContent, dict):
                    return result.structuredContent
                for block in result.content:
                    if block.type == "text":
                        payload = json.loads(block.text)
                        if isinstance(payload, dict):
                            return payload
                raise ValueError(f"Tutu MCP {name} returned no JSON object")

    def call(self, name: str, args: dict) -> dict:
        return asyncio.run(asyncio.wait_for(self._call(name, args), timeout=self.timeout_seconds))

    def search_avia(self, *, origin: str, destination: str, date: str, adults: int = 1, limit: int = 10) -> dict:
        return self.call("search_avia", {
            "origin": origin, "destination": destination, "departure_date": date,
            "adults": max(1, min(int(adults), 9)), "page_size": max(1, min(int(limit), 30)),
            "sort": "price_asc", "view": "compact",
        })

    def search_rail(self, *, origin: str, destination: str, date: str,
                    passengers: int = 1, limit: int = 10) -> dict:
        return self.call("search_rail", {
            "origin": origin, "destination": destination, "departure_date": date,
            "passengers": max(1, min(int(passengers), 6)),
            "page_size": max(1, min(int(limit), 30)),
            "sort": "price_asc", "view": "compact",
        })

    def search_hotels(self, *, city: str, check_in: str, check_out: str,
                      adults: int = 1, limit: int = 10, hotel_amenities: list[str] | None = None,
                      price_max: int | None = None) -> dict:
        args = {
            "city_name": city, "check_in": check_in, "check_out": check_out,
            "adults": max(1, min(int(adults), 6)), "page_size": max(1, min(int(limit), 30)),
            "view": "compact",
        }
        if hotel_amenities:
            args["hotel_amenities"] = hotel_amenities
        if price_max is not None:
            args["price_max"] = max(0, int(price_max))
        return self.call("search_hotels", args)
