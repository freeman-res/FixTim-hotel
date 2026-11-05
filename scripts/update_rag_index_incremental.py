"""Add new catalog hotels to an existing BGE-M3 index without re-embedding old rows.

The original index remains as a dated backup inside data/ until manually removed.
Existing hotel descriptions are not refreshed; use build_rag_index.py for that.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.catalog.rag.documents import build_hotel_documents, chunks_to_dicts
from backend.app.catalog.rag.provider import EmbeddingsProvider, make_provider
from backend.app.catalog.rag.store import VectorStore


def _existing_vectors(store: VectorStore) -> np.ndarray:
    if store.vectors is not None:
        vectors = np.asarray(store.vectors, dtype="float32")
    elif store._faiss_index is not None:
        vectors = store._faiss_index.reconstruct_n(0, store._faiss_index.ntotal)
    else:
        raise ValueError("Existing index contains no vectors")
    if len(vectors) != len(store.metadata):
        raise ValueError("Existing vectors and metadata have different lengths")
    return vectors


def update_index(hotels_path: Path, index_dir: Path,
                 embeddings: EmbeddingsProvider | None = None) -> dict:
    hotels_path, index_dir = Path(hotels_path), Path(index_dir)
    store = VectorStore(index_dir)
    if not store.load():
        raise FileNotFoundError(f"Existing RAG index not found: {index_dir}")
    provider = embeddings or make_provider()
    if store.manifest.get("embeddings_model") != provider.model_name:
        raise ValueError("Existing RAG index uses a different embedding model")
    old_vectors = _existing_vectors(store)
    if old_vectors.shape[1] != int(store.manifest.get("dim", 0)):
        raise ValueError("Existing RAG index has a dimension mismatch")

    hotels = json.loads(hotels_path.read_text(encoding="utf-8"))
    if not isinstance(hotels, list):
        raise ValueError("hotels.json must contain a list")
    indexed_ids = {item["hotel_id"] for item in store.metadata}
    additions = [chunk for chunk in build_hotel_documents(hotels)
                 if chunk.hotel_id not in indexed_ids]
    if not additions:
        return {"status": "unchanged", "added_chunks": 0,
                "unique_hotels": len(indexed_ids)}

    batches = []
    for start in range(0, len(additions), 32):
        batch = additions[start:start + 32]
        vectors = np.asarray(provider.encode([chunk.text for chunk in batch]), dtype="float32")
        if vectors.ndim != 2 or vectors.shape != (len(batch), old_vectors.shape[1]):
            raise ValueError("New embedding vectors have an unexpected shape")
        batches.append(vectors)
        if (start // 32) % 25 == 0 or start + len(batch) == len(additions):
            print(f"Embedded {start + len(batch)}/{len(additions)} new chunks", flush=True)

    vectors = np.concatenate([old_vectors, *batches], axis=0)
    metadata = store.metadata + chunks_to_dicts(additions)
    manifest = dict(store.manifest)
    manifest.update({
        "built_at": datetime.now(timezone.utc).isoformat(),
        "chunks": len(metadata),
        "unique_hotels": len({item["hotel_id"] for item in metadata}),
        "source_files": [hotels_path.name],
        "incremental_added_chunks": len(additions),
    })
    manifest.setdefault("notes", []).append(
        "New hotel IDs were added; existing hotel metadata was not re-embedded"
    )

    suffix = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:6]
    staging = index_dir.with_name(index_dir.name + "_staging_" + suffix)
    backup = index_dir.with_name(index_dir.name + "_backup_" + suffix)
    new_store = VectorStore(staging)
    new_store.save(vectors, metadata, manifest)
    verification = VectorStore(staging)
    if not verification.load() or len(verification.metadata) != len(metadata):
        raise RuntimeError(f"New index failed validation; original remains at {index_dir}")

    index_dir.rename(backup)
    try:
        staging.rename(index_dir)
    except Exception:
        backup.rename(index_dir)
        raise
    return {"status": "updated", "added_chunks": len(additions),
            "unique_hotels": manifest["unique_hotels"], "backup": str(backup)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hotels", type=Path, default=ROOT / "data/catalog/hotels.json")
    parser.add_argument("--index", type=Path, default=ROOT / "data/vector_index")
    args = parser.parse_args()
    result = update_index(args.hotels, args.index)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
