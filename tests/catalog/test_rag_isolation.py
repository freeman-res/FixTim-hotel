import json
import numpy as np
import pytest
from backend.app.catalog.rag.provider import (EmbeddingsProvider, UnavailableProvider,)
from backend.app.catalog.rag.indexer import build_index
from backend.app.catalog.rag.retriever import Retriever
from backend.app.catalog.rag.store import VectorStore
class FakeEmbeddings(EmbeddingsProvider):
    """ Простейший bag-of-chars: не семантический, но детерминированный
    и достаточный для проверки изоляции/контракта retriever'а. """
    dim = 4
    model_name = "fake-test"

    def encode(self, texts):
        out = []
        for t in texts:
            v = np.zeros(4, dtype="float32")
            for i, ch in enumerate(t):
                v[i % 4] += ord(ch) % 100
            out.append(v)
        return np.vstack(out)

@pytest.fixture
def rag_index_dir(tmp_path):
    """Строит настоящий RAG-индекс на 2 отелях с FakeEmbeddings."""
    hotels = [
        {"hotel_id": "hotel_t_001", "name": "Alpine Resort",
         "search_text": "уютный отель с парковкой",
         "location": {"city": "Москва"},
         "source": {"name": "t", "type": "demo", "retrieved_at": "2026"},
         "is_demo": True},
        {"hotel_id": "hotel_t_002", "name": "Budget Stay",
         "search_text": "дешёвый хостел рядом с метро",
         "location": {"city": "Москва"},
         "source": {"name": "t", "type": "demo", "retrieved_at": "2026"},
         "is_demo": True},
    ]
    hotels_path = tmp_path / "hotels.json"
    hotels_path.write_text(json.dumps(hotels, ensure_ascii=False), encoding="utf-8")

    index_dir = tmp_path / "vector_index"
    build_index(hotels_path, index_dir, embeddings=FakeEmbeddings())
    return index_dir


def test_retriever_filters_by_hotel_ids(rag_index_dir):
    """
    Ищем по hotel_t_001 — в результатах не должно быть hotel_t_002,
    даже если его score оказался бы выше.
    """
    r = Retriever(rag_index_dir, embeddings=FakeEmbeddings())
    hits = r.retrieve("query", ["hotel_t_001"], top_k=10)
    assert len(hits) > 0
    assert all(h["hotel_id"] == "hotel_t_001" for h in hits)


def test_vector_store_finds_allowed_hotel_outside_global_top_100(tmp_path):
    """A strict hotel filter must search the hotel's own chunks, even at low global rank."""
    store = VectorStore(tmp_path / "index")
    vectors = np.array([[1.0, 0.0]] * 100 + [[0.0, 1.0]], dtype="float32")
    metadata = [
        {"hotel_id": f"decoy_{i}", "chunk_id": f"decoy_{i}__0", "text": "decoy"}
        for i in range(100)
    ] + [{"hotel_id": "wanted", "chunk_id": "wanted__0", "text": "wanted"}]
    store.save(vectors, metadata, {"dim": 2, "embeddings_model": "test"})
    assert store.load()

    hits = store.search(np.array([[1.0, 0.0]], dtype="float32"), top_k=1,
                        allowed_hotel_ids={"wanted"})
    assert [hit["hotel_id"] for hit in hits] == ["wanted"]

def test_retriever_unknown_hotel_id_returns_empty(rag_index_dir):
    """hotel_id нет в индексе → [] (а не «дадим хоть что-то»)."""
    r = Retriever(rag_index_dir, embeddings=FakeEmbeddings())
    assert r.retrieve("query", ["hotel_unknown"], top_k=5) == []

def test_retriever_every_hit_has_source(rag_index_dir):
    """ТЗ п.5: текст без source — не доказательство. Не должен пройти."""
    r = Retriever(rag_index_dir, embeddings=FakeEmbeddings())
    for h in r.retrieve("query", [], top_k=10):
        assert h.get("source"), f"hit без source: {h}"

def test_retriever_marks_text_as_derived(rag_index_dir):
    """
    ТЗ п.5: не выдавать синтетику за отзыв.
    source.type должен быть 'derived', note — про то, что это не review.
    """
    r = Retriever(rag_index_dir, embeddings=FakeEmbeddings())
    hits = r.retrieve("query", [], top_k=10)
    for h in hits:
        assert h["source"]["type"] == "derived"
        assert "not_user_review" in (h.get("note") or "")




def test_retriever_returns_empty_without_index(tmp_path):
    """Индекса нет — available=False, retrieve → [] (без exception)."""
    r = Retriever(tmp_path / "nonexistent", embeddings=FakeEmbeddings())
    assert r.available is False
    assert r.retrieve("query", ["hotel_t_001"]) == []

def test_retriever_returns_empty_without_embeddings(rag_index_dir):
    """Индекс есть, embeddings №2 недоступны — [] (без exception)."""
    r = Retriever(rag_index_dir, embeddings=UnavailableProvider("test disabled"))
    assert r.retrieve("уютный отель", ["hotel_t_001"]) == []

@pytest.mark.asyncio
async def test_gateway_find_offers_works_without_rag(gateway):
    """
    Главный инвариант ТЗ п.2: если RAG не построен,
    find_offers продолжает работать, retrieve_reviews даёт [].
    """
    hotels = await gateway.find_offers({})
    assert len(hotels) == 3
    reviews = await gateway.retrieve_reviews("query", ["hotel_t_001"])
    assert reviews == []
