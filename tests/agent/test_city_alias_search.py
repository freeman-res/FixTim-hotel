import asyncio

from backend.app.agent.schemas import SearchFilters, SearchHotelsArgs
from backend.app.agent.tools.search_hotels import search_hotels


class Catalog:
    async def find_offers(self, filters):
        return [{"hotel_id": "spb-1", "name": "Отель", "location": {"city": "Санкт-Петербург"}}]


def test_piter_alias_survives_ranking():
    result = asyncio.run(search_hotels(
        SearchHotelsArgs(filters=SearchFilters(city="Питер")),
        Catalog(), {"trip": {"city": "Питер", "nights": 4}},
    ))
    assert result["count"] == 1
    assert result["filters"]["city"] == "Санкт-Петербург"
