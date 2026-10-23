#Векторное хранилище на ChromaDB 
#PersistentClient сохраняет индекс на диск — при повторном запуске эмбеддинги не пересчитываются.
import chromadb
class VectorStore:
    #Обёртка над ChromaDB с фильтром по hotel_id.
    def __init__( self,path: str = "data/vector_index", collection_name: str = "reviews",):
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(collection_name)

    def reset(self) -> None:
        #Удаляет коллекцию и создаёт заново. Нужно при пересборке индекса.
        self.client.delete_collection(self.collection.name)
        self.collection = self.client.get_or_create_collection(self.collection.name)

    def add(self,ids: list[str],documents: list[str],metadatas: list[dict], embeddings: list[list[float]], ) -> None:
       #Добавляет чанки в коллекцию.
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings)

    def query(self,embedding: list[float],top_k: int = 5, hotel_ids: list[int] | None = None) -> dict:
    #Ищет top_k ближайших векторов.
    #Если hotel_ids заданы — фильтрует по ним через where.
        where = None
        if hotel_ids:
            where = {"hotel_id": {"$in": [int(h) for h in hotel_ids]}}

        return self.collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, self.count()),
            where=where)

    def count(self) -> int:
    #Количество чанков в коллекции.
        return self.collection.count()