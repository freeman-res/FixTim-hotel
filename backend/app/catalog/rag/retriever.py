"""
Поиск по смыслу. ТЗ№3 п.5:
    retrieve_reviews(query, hotel_ids, top_k=5) -> тексты + hotel_id + source
Требования:
  - Результаты не должны содержать отзывы ДРУГОГО отеля.
  - Тексты без надёжной привязки к источнику нельзя выдавать за доказательство.
"""

import logging

from .embeddings import EmbeddingsProvider, make_provider
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
        # Жёсткий фильтр: пустой hotel_ids означает "искать везде",
        # но ТЗ требует "не возвращать чужих отелей" — фильтр явный.
        allowed = set(hotel_ids) if hotel_ids else None

        try:
            q_vec = self.embeddings.encode([query])
        except RuntimeError as exc:
            log.warning("Embeddings недоступны: %s", exc)
            return []
        hits = self.store.search(q_vec, top_k=top_k, allowed_hotel_ids=allowed)
        # Дополнительный фильтр (sanity check на всякий случай — фильтр
        # уже применён в store.search, но проверим ещё раз в retriever).
        if allowed:
            hits = [h for h in hits if h.get("hotel_id") in allowed]
        # Формат ответа: явно отделяем "чужое" от "нашего".
        return [ {"hotel_id": h["hotel_id"],
                "chunk_id": h["chunk_id"],
                "text": h["text"],
                "score": h["score"],
                "source": h["source"],
                "is_demo": h["is_demo"],
                "note": h.get("note"),
            } for h in hits]