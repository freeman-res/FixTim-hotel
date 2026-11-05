import asyncio
import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.agent.schemas import TripPatch, SearchFilters, SearchHotelsArgs
from backend.app.agent.state_manager import StateManager
from backend.app.agent.ranking.scorer import rank_offers
from backend.app.agent.tools.search_hotels import search_hotels
from backend.app.agent.tools.registry import ToolRegistry
from backend.app.agent.tools.executor import ToolExecutor
from backend.app.catalog.rag.embeddings import Embedder


class FakeCatalog:
    def __init__(self):
        self.filters = None
        self.offers = [
            {"hotel_id": "h1", "offer_id": "o1", "name": "Демо: Тихий сад", "city": "Сочи", "total_price": 21000, "currency": "RUB", "rating": 4.6, "amenities": ["pool", "wifi"], "semantic_score": .9},
            {"hotel_id": "h2", "offer_id": "o2", "name": "Демо: Центр", "city": "Сочи", "total_price": 33000, "currency": "RUB", "rating": 4.9, "amenities": ["wifi"], "semantic_score": .8},
            {"hotel_id": "h3", "offer_id": "o3", "name": "Демо: Москва", "city": "Москва", "total_price": 12000, "currency": "RUB", "rating": 4.7, "amenities": ["pool"], "semantic_score": .7},
        ]

    async def find_offers(self, filters):
        self.filters = filters
        return self.offers

    async def get_hotel(self, hotel_id):
        return next((hotel for hotel in self.offers if hotel["hotel_id"] == str(hotel_id)), None)

    async def get_hotels_by_ids(self, hotel_ids):
        return [hotel for hotel in self.offers if hotel["hotel_id"] in hotel_ids]

    async def retrieve_reviews(self, query, hotel_ids, top_k=5):
        return [{"hotel_id": "h1", "text": "Ночью было очень тихо", "source": "review-1"},
                {"hotel_id": "h99", "text": "Чужой отель", "source": "review-2"}]


@dataclass
class FakeCallFunction:
    name: str
    arguments: dict


@dataclass
class FakeCall:
    function: FakeCallFunction


class FakeMessage:
    def __init__(self, content="", calls=None):
        self.content = content
        self.tool_calls = calls or []

    def model_dump(self, **kwargs):
        return {"role": "assistant", "content": self.content, "tool_calls": [
            {"function": {"name": c.function.name, "arguments": c.function.arguments}} for c in self.tool_calls
        ]}


class FakeLLM:
    def __init__(self, patch):
        self.patch = patch
        self.tool_round = 0

    async def chat(self, messages, tools=None, response_format=None):
        if response_format is not None:
            return SimpleNamespace(message=FakeMessage(self.patch.model_dump_json()))
        self.tool_round += 1
        if self.tool_round == 1:
            return SimpleNamespace(message=FakeMessage(calls=[FakeCall(FakeCallFunction("search_hotels", {
                "filters": {"city": "Сочи", "max_total_price": 999999},
                "preferences": ["quiet"], "limit": 5,
            }))]))
        return SimpleNamespace(message=FakeMessage(content="Подобрал подтверждённые варианты."))


def run(coroutine):
    return asyncio.run(coroutine)


def test_state_patch_retains_original_constraints_and_rejection():
    state = {"trip": {"city": "Сочи", "check_in": "2026-11-12", "check_out": "2026-11-15", "guests": 2, "max_total_price": 30000},
             "last_hotel_ids": ["h1", "h2"]}
    updated = StateManager.update(state, TripPatch(required_amenities=["pool"], reject_result_numbers=[2]))
    assert updated["trip"]["city"] == "Сочи"
    assert updated["trip"]["guests"] == 2
    assert updated["trip"]["required_amenities"] == ["pool"]
    assert updated["rejected_hotel_ids"] == ["h2"]
    assert "rejected_hotel_ids" not in state


def test_change_dates_computes_nights():
    state = {"trip": {"city": "Сочи", "check_in": "2026-11-12", "check_out": "2026-11-15", "nights": 3}}
    new = StateManager.update(state, TripPatch(check_out="2026-11-20"))
    assert new["trip"]["nights"] == 8


def test_missing_required_fields():
    assert StateManager.missing_fields({"trip": {"city": "Сочи"}}) == []
    assert StateManager.missing_fields({"trip": {}}) == ["город"]


def test_ranking_rejects_hard_violations():
    ranked = rank_offers(FakeCatalog().offers,
                         {"city": "Сочи", "currency": "RUB", "required_amenities": ["pool"], "max_total_price": 30000},
                         ["quiet"], set())
    assert [h["hotel_id"] for h in ranked] == ["h1"]
    assert ranked[0]["match_score"] > 0


def test_tool_uses_session_filters_and_never_loosens_them():
    catalog = FakeCatalog()
    state = {"trip": {"city": "Сочи", "max_total_price": 30000, "required_amenities": ["pool"], "currency": "RUB"}}
    args = SearchHotelsArgs(filters=SearchFilters(city="Москва", max_total_price=999999))
    result = run(search_hotels(args, catalog, state))
    assert catalog.filters["city"] == "Сочи"
    assert catalog.filters["max_total_price"] == 30000
    assert [h["hotel_id"] for h in result["hotels"]] == ["h1"]


def test_agent_end_to_end_offline_mock():
    catalog = FakeCatalog()
    agent = AgentOrchestrator(catalog=catalog, llm=FakeLLM(TripPatch(required_amenities=["pool"])))
    state = {"trip": {"city": "Сочи", "check_in": "2026-11-12", "check_out": "2026-11-15", "guests": 2, "max_total_price": 30000, "currency": "RUB"}}
    result = run(agent.handle_message("session-1", "Теперь обязательно бассейн", state))
    assert result.status == "results"
    assert [h["hotel_id"] for h in result.hotels] == ["h1"]
    assert result.updated_state["trip"]["max_total_price"] == 30000
    assert result.updated_state["last_hotel_ids"] == ["h1"]


def test_catalog_hotel_search_does_not_require_availability_dates():
    catalog = FakeCatalog()
    agent = AgentOrchestrator(catalog=catalog, llm=FakeLLM(TripPatch(city="Казань")))
    result = run(agent.handle_message("id", "Найди в Казани", {}))
    assert result.status == "no_results"
    assert not result.hotels
    assert result.updated_state["trip"]["city"] == "Казань"
    assert catalog.filters.get("check_in") is None


def test_train_source_failure_is_not_returned_as_no_results():
    from rzd_api import RzdTransportError

    class Catalog:
        async def find_transport(self, _filters):
            raise RzdTransportError("network unavailable")

    class ToolLLM:
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools=None, response_format=None):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(message=FakeMessage(calls=[FakeCall(FakeCallFunction(
                    "search_transport", {"from_city": "Москва", "to_city": "Казань",
                                         "type": "train", "date_from": "2026-11-04"}
                ))]))
            return SimpleNamespace(message=FakeMessage(content="Поездов нет."))

    agent = AgentOrchestrator(catalog=Catalog(), llm=ToolLLM())
    result = run(agent._tool_loop({"trip": {}}, "Москва — Казань 4 ноября", "trip_search", "id"))

    assert result.status == "error"
    assert not result.transport_options
    assert "недоступен" in result.reply


def test_disallowed_tool_cannot_run():
    result = run(ToolExecutor(ToolRegistry()).execute("run_shell", {"cmd": "whoami"}))
    assert not result["ok"]
    assert result["error"] == "unknown_tool"


class FakeEmbeddingClient:
    def embed(self, model, input):
        return {"embeddings": [[float(i), 0.0] for i, _ in enumerate(input)]}


def test_embedding_batches_and_empty_input():
    embedder = Embedder(client=FakeEmbeddingClient(), batch_size=2)
    assert embedder.encode([]) == []
    vectors = embedder.encode(["a", "b", "c"])
    assert len(vectors) == 3
    assert embedder.dim == 2
    with pytest.raises(ValueError):
        embedder.encode(["", "a"])
