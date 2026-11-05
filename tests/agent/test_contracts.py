"""Дополнительные автономные тесты модулей №2; сервис №3 не требуется."""
import asyncio
from types import SimpleNamespace

import pytest

from backend.app.agent.schemas import (
    CompareHotelsArgs, SearchReviewsArgs, SearchHotelsArgs, SearchFilters,
)
from backend.app.agent.state_manager import StateManager
from backend.app.agent.tools.executor import ToolExecutor
from backend.app.agent.tools.factory import build_registry
from backend.app.agent.tools.compare_hotels import compare_hotels
from backend.app.agent.tools.search_reviews import search_reviews
from backend.app.agent.ranking.scorer import rank_offers
from backend.app.catalog.rag.embeddings import Embedder


class DemoCatalog:
    async def find_offers(self, filters):
        return []

    async def get_hotel(self, hotel_id):
        return {"hotel_id": hotel_id}

    async def get_hotels_by_ids(self, hotel_ids):
        return [{"hotel_id": h, "name": f"Демо {h}", "rating": 4.5, "secret": "не показывать"} for h in hotel_ids]

    async def retrieve_reviews(self, query, hotel_ids, top_k=5):
        return [
            {"hotel_id": "h1", "source": "review-1", "text": "Тихо"},
            {"hotel_id": "h2", "source": "review-2", "text": "Ночью шумно"},
            {"hotel_id": "h1", "text": "Без источника"},
        ]


def run(awaitable):
    return asyncio.run(awaitable)


def test_registry_provides_tool_schemas():
    registry = build_registry(DemoCatalog(), {})
    schemas = registry.ollama_schemas()
    assert {t["function"]["name"] for t in schemas} == {
        "search_hotels", "get_hotel_details", "search_reviews", "compare_hotels",
        "search_transport", "search_hotel_descriptions",
        "get_weather",
    }
    assert all(t["function"]["parameters"].get("properties") for t in schemas)
    descriptions = {t["function"]["name"]: t["function"]["description"] for t in schemas}
    assert "price_references" in descriptions["search_hotels"]
    assert "не актуальная цена" in descriptions["search_hotels"]


def test_executor_rejects_invalid_tool_arguments():
    executor = ToolExecutor(build_registry(DemoCatalog(), {}))
    result = run(executor.execute("search_hotels", {"filters": {}, "limit": 1000}))
    assert result["ok"] is False
    assert result["error"] == "invalid_arguments"


def test_reviews_only_return_requested_hotels_with_evidence():
    out = run(search_reviews(SearchReviewsArgs(hotel_ids=["h1"], query="тишина"), DemoCatalog()))
    assert out["count"] == 1
    assert out["matches"][0]["source"] == "review-1"


def test_compare_does_not_leak_unrequested_fields():
    out = run(compare_hotels(CompareHotelsArgs(hotel_ids=["h1", "h2"]), DemoCatalog()))
    assert len(out["hotels"]) == 2
    assert all("secret" not in hotel for hotel in out["hotels"])


def test_compare_exposes_archival_price_reference_with_its_unknown_context():
    class CatalogWithPriceReference(DemoCatalog):
        async def get_hotels_by_ids(self, hotel_ids):
            return [{
                "hotel_id": "h1",
                "name": "Отель Север",
                "price": None,
                "total_price": None,
                "price_references": [{
                    "amount": 6800,
                    "currency": None,
                    "unit": None,
                    "status": "unverified_reference",
                }],
                "guest_rating": {"score": 9.1, "scale": None},
                "private_field": "must not leak",
            }]

    out = run(compare_hotels(CompareHotelsArgs(hotel_ids=["h1", "h2"]), CatalogWithPriceReference()))
    hotel = out["hotels"][0]
    assert hotel["price"] is None
    assert hotel["total_price"] is None
    assert hotel["price_references"][0]["currency"] is None
    assert hotel["guest_rating"]["scale"] is None
    assert "private_field" not in hotel


def test_rank_rejects_wrong_currency_but_keeps_unknown_price_unconfirmed():
    offers = [
        {"hotel_id": "h1", "city": "Сочи", "total_price": 100, "currency": "USD"},
        {"hotel_id": "h2", "city": "Сочи", "total_price": None, "currency": "RUB",
         "price_references": [{"amount": 100, "status": "unverified_reference"}]},
        {"hotel_id": "h3", "city": "Сочи", "total_price": 1000, "currency": "RUB"},
    ]
    ranked = rank_offers(offers, {"city": "Сочи", "currency": "RUB", "max_total_price": 2000}, [], set())
    assert [hotel["hotel_id"] for hotel in ranked] == ["h3", "h2"]
    assert "не подтверждено" in ranked[1]["reason"]


def test_history_keeps_last_sixteen_messages():
    state = {}
    for i in range(10):
        state = StateManager.add_history(state, f"u{i}", f"a{i}")
    assert len(state["history"]) == 16
    assert state["history"][0]["content"] == "u2"


def test_reject_non_uniform_embedding_dimensions():
    class BrokenClient:
        def embed(self, model, input):
            return {"embeddings": [[0.1] * (3 if i else 2) for i, _ in enumerate(input)]}
    encoder = Embedder(client=BrokenClient())
    with pytest.raises(RuntimeError, match="размерности"):
        encoder.encode(["a", "b"])
