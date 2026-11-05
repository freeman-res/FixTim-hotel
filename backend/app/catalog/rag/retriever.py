
import logging

from .provider import EmbeddingsProvider, make_provider
from .store import VectorStore

log = logging.getLogger(__name__)


class Retriever:
    def __init__(self, index_dir, embeddings: EmbeddingsProvider | None = None):
        self.store = VectorStore(index_dir)
        self._loaded = self.store.load()
        self.embeddings = embeddings or make_provider()

    @property
    def available(self) -> bool:
        return self._loaded

    def retrieve(self, query: str, hotel_ids: list[str], top_k: int = 5) -> list[dict]:
        if not self._loaded:
            log.warning("RAG-индекс не загружен — пустой результат")
            return []
        if not query or not query.strip():
            return []


        allowed = set(hotel_ids) if hotel_ids else None

        try:
            q_vec = self.embeddings.encode([query])
        except Exception as exc:
            log.warning("Embeddings недоступны: %s", exc)
            return []
        expected_dim = self.store.manifest.get("dim")
        expected_model = self.store.manifest.get("embeddings_model")
        if expected_dim and q_vec.shape[1] != int(expected_dim):
            log.error("Размерность запроса %s не совпадает с индексом %s", q_vec.shape[1], expected_dim)
            return []
        if expected_model and self.embeddings.model_name != expected_model:
            log.error("Модель запроса %s не совпадает с индексом %s", self.embeddings.model_name, expected_model)
            return []
        hits = self.store.search(q_vec, top_k=top_k, allowed_hotel_ids=allowed)


        if allowed:
            hits = [h for h in hits if h.get("hotel_id") in allowed]

        return [ {"hotel_id": h["hotel_id"],
                "chunk_id": h["chunk_id"],
                "text": h["text"],
                "score": h["score"],
                "source": h["source"],
                "is_demo": h["is_demo"],
                "note": h.get("note"),
            } for h in hits]
