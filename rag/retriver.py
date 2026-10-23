# Семантический поиск по отзывам
#retrieve_reviews(query, hotel_ids, top_k) — async-функция,
from contracts.evidence import ReviewChunk
from .embeddings import Embedder
from .store import VectorStore
class ReviewRetriever:
    #Семантический поиск по индексированным отзывам.
    def __init__(self, store: VectorStore, embedder: Embedder):
        self.store = store
        self.embedder = embedder
    async def retrieve_reviews(
        self,
        query: str,
        hotel_ids: list[int] | None = None,
        top_k: int = 5,) -> list[ReviewChunk]:
        # Ищет отзывы, близкие по смыслу к запросу.
        if not query or not query.strip():
            return []
        if self.store.count() == 0:
            return []
        # Запрос → вектор
        query_embedding = self.embedder.encode([query])[0]

        # Поиск в store
        result = self.store.query(
            embedding=query_embedding,
            top_k=top_k,
            hotel_ids=hotel_ids,)

        #  Развернуть результат Chroma в список ReviewChunk
        # Chroma возвращает списки внутри списков: documents[0], metadatas[0], distances[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        chunks = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            chunks.append(ReviewChunk(
                hotel_id=int(meta["hotel_id"]),
                text=doc,
                source=meta.get("source", "unknown"),
                score=float(1.0 - dist),   ))# distance → score (больше = лучше)
        return chunks