import json

import numpy as np

from backend.app.catalog.rag.indexer import build_index
from backend.app.catalog.rag.provider import EmbeddingsProvider
from backend.app.catalog.rag.retriever import Retriever
from backend.app.catalog.rag.store import VectorStore
from scripts.update_rag_index_incremental import update_index


class FakeEmbeddings(EmbeddingsProvider):
    model_name = "fake"
    dim = 4

    def __init__(self):
        self.calls = []

    def encode(self, texts):
        self.calls.extend(texts)
        rows = []
        for text in texts:
            row = np.zeros(4, dtype="float32")
            for index, char in enumerate(text):
                row[index % 4] += ord(char) % 17
            rows.append(row)
        return np.stack(rows)


def test_incremental_rag_adds_only_missing_hotels_and_preserves_existing(tmp_path):
    hotels_path = tmp_path / "hotels.json"
    old = [{"hotel_id": "h1", "name": "Отель Старый", "location": {"city": "Казань"},
            "search_text": "старый центр Казани", "is_demo": False}]
    hotels_path.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    index_dir = tmp_path / "vector_index"
    build_index(hotels_path, index_dir, embeddings=FakeEmbeddings())

    new = old + [{"hotel_id": "h2", "name": "Отель Новый", "location": {"city": "Казань"},
                  "search_text": "новый тихий отель в Казани", "is_demo": False}]
    hotels_path.write_text(json.dumps(new, ensure_ascii=False), encoding="utf-8")
    embedder = FakeEmbeddings()
    result = update_index(hotels_path, index_dir, embeddings=embedder)
    assert result["added_chunks"] == 1
    assert len(embedder.calls) == 1
    store = VectorStore(index_dir)
    assert store.load()
    assert {item["hotel_id"] for item in store.metadata} == {"h1", "h2"}
    assert store.manifest["unique_hotels"] == 2
    assert Retriever(index_dir, embeddings=FakeEmbeddings()).retrieve("новый", ["h2"], top_k=1)[0]["hotel_id"] == "h2"
    assert update_index(hotels_path, index_dir, embeddings=FakeEmbeddings())["added_chunks"] == 0
