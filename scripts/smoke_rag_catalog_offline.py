#!/usr/bin/env python3
"""Structural RAG check over the real hotel catalog using fake local vectors.

This verifies document creation, index persistence and retrieval plumbing only.
The test embedder is not semantic and does not create the runtime index.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.catalog.rag.indexer import build_index
from backend.app.catalog.rag.provider import EmbeddingsProvider
from backend.app.catalog.rag.retriever import Retriever


class SmokeEmbeddings(EmbeddingsProvider):
    """Deterministic vectors for pipeline validation, not semantic search."""

    dim = 4
    model_name = "offline-smoke-only"

    def encode(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            vector = np.zeros(self.dim, dtype="float32")
            for index, char in enumerate(text):
                vector[index % self.dim] += ord(char) % 101
            rows.append(vector)
        return np.vstack(rows)


def main() -> int:
    hotels_path = ROOT / "data" / "catalog" / "hotels.json"
    if not hotels_path.is_file():
        raise SystemExit("Каталог не найден. Сначала запусти scripts/import_data.py")
    hotels = json.loads(hotels_path.read_text(encoding="utf-8"))
    if not isinstance(hotels, list) or not hotels:
        raise SystemExit("data/catalog/hotels.json должен содержать непустой список")

    with tempfile.TemporaryDirectory(prefix="hotel-rag-offline-smoke-") as temp:
        index_dir = Path(temp) / "vector_index"
        build = build_index(hotels_path, index_dir, embeddings=SmokeEmbeddings())
        retriever = Retriever(index_dir, embeddings=SmokeEmbeddings())
        hits = retriever.retrieve("отель в Москве с парковкой", [], top_k=3)
        if build.get("chunks", 0) < len(hotels):
            raise SystemExit(
                f"Часть отелей не получила документ: {build.get('chunks')} чанков / {len(hotels)} отелей"
            )
        if not retriever.available or not hits:
            raise SystemExit("Временный индекс не загрузился или поиск не вернул фрагменты")
        if any(item.get("source", {}).get("type") != "derived" for item in hits):
            raise SystemExit("Найдены фрагменты без derived provenance")
        print(f"hotel_rows={len(hotels)} chunks={build['chunks']} temporary_hits={len(hits)}")
        print("PASS: каталог проходит через RAG document/index/retriever pipeline")
        print("NOTE: vectors are fake; this does not verify BGE-M3 quality or runtime readiness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
