"""Дополнительные офлайн-тесты зоны ответственности №2 (без Ollama)."""
import asyncio
import pytest
from pydantic import ValidationError

from backend.app.agent.schemas import (
    TripPatch, SearchHotelsArgs, SearchReviewsArgs, CompareHotelsArgs,
)
from backend.app.agent.state_manager import StateManager
from backend.app.agent.tools.registry import ToolRegistry
from backend.app.agent.tools.executor import ToolExecutor
from backend.app.agent.tools.factory import build_registry
from backend.app.agent.tools.search_reviews import search_reviews
from backend.app.agent.ranking.scorer import rank_offers


class DummyCatalog:
    def __init__(self):
        self.offers = [
            {"hotel_id": "1", "name": "С бассейном", "city": "Сочи", "currency": "RUB", "total_price": 24000, "amenities": ["pool"]},
            {"hotel_id": "2", "name": "Без цены", "city": "Сочи", "currency": "RUB", "total_price": None, "amenities": ["pool"]},
        ]

    async def find_offers(self, filters):
        return self.offers

    async def get_hotel(self, hotel_id):
        return self.offers[0]

    async def get_hotels_by_ids(self, hotel_ids):
        return [hotel for hotel in self.offers if hotel["hotel_id"] in hotel_ids]

    async def retrieve_reviews(self, query, hotel_ids, top_k=5):
        return [
            {"hotel_id": "1", "text": "Тихо", "source": "review-ok"},
            {"hotel_id": "99", "text": "Не тот отель", "source": "review-other"},
            {"hotel_id": "1", "text": "Нет источника"},
        ]


def run(awaitable):
    return asyncio.run(awaitable)


def test_invalid_schema_rejects_unreasonable_limit():
    with pytest.raises(ValidationError):
        SearchHotelsArgs(filters={}, limit=1000)


def test_restart_trip_discards_previous_fields():
    old = {"trip": {"city": "Сочи", "guests": 2}, "rejected_hotel_ids": ["1"]}
    new = StateManager.update(old, TripPatch(new_trip=True, city="Казань"))
    assert new["trip"] == {"city": "Казань"}
    assert new["rejected_hotel_ids"] == []
    assert old["trip"]["city"] == "Сочи"


def test_rank_keeps_missing_price_under_maximum_as_unconfirmed():
    offers = DummyCatalog().offers
    result = rank_offers(offers, {"city": "Сочи", "max_total_price": 30000}, [], set())
    assert [hotel["hotel_id"] for hotel in result] == ["1", "2"]
    assert "не подтверждено" in result[1]["reason"]


def test_rank_excludes_rejected_hotel():
    result = rank_offers(DummyCatalog().offers, {"city": "Сочи"}, [], {"1"})
    assert [hotel["hotel_id"] for hotel in result] == ["2"]


def test_executor_rejects_invalid_arguments_before_calling_catalog():
    registry = build_registry(DummyCatalog(), {"trip": {}})
    result = run(ToolExecutor(registry).execute("search_reviews", {"hotel_ids": [], "query": "тихо"}))
    assert result["error"] == "invalid_arguments"


def test_search_reviews_discards_other_hotel_and_missing_source():
    args = SearchReviewsArgs(hotel_ids=["1"], query="тихо")
    result = run(search_reviews(args, DummyCatalog()))
    assert result["count"] == 1
    assert result["matches"][0]["source"] == "review-ok"


def test_ids_can_be_int_in_review_and_comparison():
    review = SearchReviewsArgs(hotel_ids=[1, 2], query="тихо")
    compare = CompareHotelsArgs(hotel_ids=[1, 2])
    assert review.hotel_ids == ["1", "2"]
    assert compare.hotel_ids == ["1", "2"]


def test_tool_registry_has_all_supported_tools():
    names = {item["function"]["name"] for item in build_registry(DummyCatalog(), {}).ollama_schemas()}
    assert names == {"search_hotels", "get_hotel_details", "search_reviews", "compare_hotels",
                     "search_transport", "search_hotel_descriptions", "get_weather"}
