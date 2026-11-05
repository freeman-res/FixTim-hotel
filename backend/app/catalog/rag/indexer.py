""" Построение RAG-индекса: hotels.json → chunks → BGE-M3 → vector store.
Запускается ОДИН РАЗ офлайн (s
В runtime не вызывается."""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from .documents import build_hotel_documents, chunks_to_dicts
from .provider import EmbeddingsProvider, make_provider
from .store import VectorStore
log = logging.getLogger(__name__)
BATCH_SIZE = 32
def build_index(
    hotels_path: Path,
    index_dir: Path,
    embeddings: EmbeddingsProvider | None = None,) -> dict:
    hotels_path = Path(hotels_path)
    if not hotels_path.exists():
        raise FileNotFoundError(f"hotels.json не найден: {hotels_path}")

    hotels = json.loads(hotels_path.read_text(encoding="utf-8"))
    log.info("Прочитано %d отелей", len(hotels))
    chunks = build_hotel_documents(hotels)
    log.info("Собрано %d чанков", len(chunks))
    if not chunks:
        log.warning("Нет текстов для индексации — пустой индекс")
        return {"status": "empty", "chunks": 0}

    provider = embeddings or make_provider()
    texts = [c.text for c in chunks]
    batches: list[np.ndarray] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        vecs = provider.encode(batch)
        batches.append(np.asarray(vecs, dtype="float32"))
        log.info("Эмбеддинги: %d/%d",
                 min(i + BATCH_SIZE, len(texts)), len(texts))
    vectors = np.vstack(batches)
    if getattr(provider, "model_name", "") == "bge-m3" and vectors.shape[1] != 1024:
        raise ValueError(f"Ожидалась размерность BGE-M3 1024, получено {vectors.shape[1]}")
    manifest = { "built_at": datetime.now(timezone.utc).isoformat(),
        "embeddings_model": getattr(provider, "model_name", "unknown"),
        "dim": int(vectors.shape[1]),
        "chunks": len(chunks),
        "unique_hotels": len({c.hotel_id for c in chunks}),
        "source_files": [hotels_path.name],
        "notes": [
            "chunks derived from hotels.json search_text and metadata",
            "NOT real user reviews; source.type=derived",
            "scores are cosine similarity (inner product on L2-normalized)",  ], }
    store = VectorStore(index_dir)
    store.save(vectors, chunks_to_dicts(chunks), manifest)
    return {"status": "ok", "chunks": len(chunks), "dim": int(vectors.shape[1])}
