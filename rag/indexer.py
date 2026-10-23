#Сборка векторного индекса 
#Связывает documents → embeddings → store в один вызов build().
from .documents import prepare_documents
from .embeddings import Embedder
from .store import VectorStore
class ReviewIndexer:
    #Строит индекс отзывов в ChromaDB.
    def __init__(self, store: VectorStore, embedder: Embedder):
        self.store = store
        self.embedder = embedder
    def build(self, reviews: list[dict], reset: bool = False) -> int:
        #Собирает индекс из списка отзывов.
        #Возвращает количество проиндексированных чанков.
        documents = prepare_documents(reviews)
        if not documents:
            return 0 
        if reset:
            self.store.reset()
        texts = [d["text"] for d in documents]
        embeddings = self.embedder.encode(texts)
        self.store.add(ids=[d["id"] for d in documents],
            documents=texts,
            metadatas=[
                {"hotel_id": d["hotel_id"], "source": d["source"]}
                for d in documents  ],embeddings=embeddings,)
        return len(documents)