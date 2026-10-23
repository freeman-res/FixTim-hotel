'''CatalogService собирает:
- провайдер данных (demo / json / csv / sql / http),
- нормализацию и валидацию,
- структурированный поиск (ExactSearch),
- RAG (ReviewIndexer + ReviewRetriever).'''
from typing import Any
from contracts.hotel import Hotel, Offer
from contracts.evidence import ReviewChunk
from contracts.search import SearchFilters
from .catalog.normalize import normalize_hotel, normalize_offer, normalize_review
from .catalog.validate import validate_hotels, validate_offers, validate_reviews
from .providers.factory import make_provider
from ..contracts.search import ExactSearch
from .rag.embeddings import Embedder
from .rag.store import VectorStore
from .rag.indexer import ReviewIndexer
from .rag.retriever import ReviewRetriever
class CatalogService:
    # Фасад над всем модулем Data/RAG.
    def __init__(self, provider_kind: str = "demo", **provider_kwargs: Any):
        # provider_kind: "demo" | "json" | "csv" | "sql" | "http"
        # provider_kwargs: аргументы для выбранного провайдера
        provider = make_provider(provider_kind, **provider_kwargs)
        # Нормализация
        raw_hotels = [normalize_hotel(h) for h in provider.load_hotels()]
        raw_offers = [normalize_offer(o) for o in provider.load_offers()]
        raw_reviews = [normalize_review(r) for r in provider.load_reviews()]
        # Валидация
        hotels = validate_hotels(raw_hotels)
        hotel_ids = {h["hotel_id"] for h in hotels}
        offers = validate_offers(raw_offers, hotel_ids)
        reviews = validate_reviews(raw_reviews, hotel_ids)
        # 4. Структурированный поиск
        self.exact = ExactSearch(hotels, offers)
        # 5. RAG — лениво: ретривер появится только после build_rag()
        self._reviews = reviews
        self._store: VectorStore | None = None
        self._embedder: Embedder | None = None
        self._retriever: ReviewRetriever | None = None

    # RAG: сборка индекса
    def build_rag(self, reset: bool = True) -> int:
# Собирает (или пересобирает) векторный индекс отзывов.
#Вызывается один раз после создания сервиса:
            svc = CatalogService("demo")
            n = svc.build_rag(reset=True)

#Возвращает количество проиндексированных чанков.
#Если отзывов нет — возвращает 0, RAG просто не будет доступен.
            self._embedder = Embedder()
            self._store = VectorStore()
            indexer = ReviewIndexer(self._store, self._embedder)
            n = indexer.build(self._reviews, reset=reset)
            self._retriever = ReviewRetriever(self._store, self._embedder)
            return n
# Интерфейс для AI-агента (пункт 6 ТЗ)
    async def find_offers(
        self,
        filters: SearchFilters | dict[str, Any],) -> list[Offer]:
#Структурированный поиск предложений.
# Принимает SearchFilters или обычный dict (для удобства агента).
#Возвращает [] если ничего не найдено.
        filters_dict = (
            filters.model_dump()
            if isinstance(filters, SearchFilters)
            else filters )
        return await self.exact.find_offers(filters_dict)
    async def get_hotel(self, hotel_id: int) -> Hotel | None:
        #Возвращает отель по id или None.
        return await self.exact.get_hotel(hotel_id)
    async def get_hotels_by_ids(self, hotel_ids: list[int]) -> list[Hotel]:
        #Возвращает список отелей по списку id. Отсутствующие пропускает.
        return await self.exact.get_hotels_by_ids(hotel_ids)
    async def retrieve_reviews(self, query: str, hotel_ids: list[int] | None = None, top_k: int = 5,) -> list[ReviewChunk]:
# Семантический поиск отзывов.
#Если RAG не собран (build_rag не вызывался) — возвращает [],
#чтобы модуль работал и без RAG .
        if self._retriever is None:
            return []
        return await self._retriever.retrieve_reviews(query, hotel_ids, top_k)