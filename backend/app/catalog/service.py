from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from datetime import date, datetime, timezone

from .climate.service import ClimateService
from .destinations.service import DestinationsService
from .hotels.service import HotelsService
from .normalize import normalize_city, normalize_filters
from .providers.factory import get_provider
from .transport.service import TransportService
from .transfers.service import TransfersService
from .validate import (
    validate_offer_filters,
    validate_transport_filters,
)

log = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class CatalogGateway:
    def __init__(self, provider=None, live_client=None):


        use_default_provider = provider is None
        self.provider = provider or get_provider()
        if live_client is None and use_default_provider and os.getenv("TUTU_MCP_ENABLED", "true").lower() in {"1", "true", "yes"}:
            from .live.tutu import TutuMcpClient
            live_client = TutuMcpClient()



        self.hotels       = HotelsService(self.provider, live_client=live_client)
        self.destinations = DestinationsService(self.provider)
        self.transport    = TransportService(self.provider, live_client=live_client)
        self.transfers    = TransfersService(self.provider)
        self.climate      = ClimateService(self.provider)


        self._retriever = None





    async def find_offers(self, filters: dict) -> list[dict]:
        """
        Структурированный поиск отелей.

        Фильтры (поддерживаемые): city, hotel_ids, stars_min, stars_max,
        price_min, price_max, amenities (dict), + любые, которые
        понимает search/exact.filter_hotels.

        Возвращает [] при невалидных фильтрах — НЕ бросает исключение,
        чтобы агент мог показать пользователю понятный ответ
        «не могу найти по таким условиям».
        """
        filters = normalize_filters(filters or {})
        errs = validate_offer_filters(filters)
        if errs:
            log.warning("find_offers: невалидные фильтры: %s", errs)
            return []
        return await asyncio.to_thread(self.hotels.find_offers, filters)

    async def get_hotel(self, hotel_id: str) -> dict | None:
        """Один отель по ID. None — если ID пустой или отель не найден."""
        if not hotel_id:
            return None
        return await asyncio.to_thread(self.hotels.get_hotel, hotel_id)

    async def get_hotels_by_ids(self, hotel_ids: list[str]) -> list[dict]:
        """
        Пачка отелей по ID. Порядок результата сохраняет порядок
        hotel_ids — предсказуемо для №2.
        """
        if not isinstance(hotel_ids, list) or not hotel_ids:
            return []
        return await asyncio.to_thread(self.hotels.get_hotels_by_ids, hotel_ids)




    async def suggest_destinations(self, filters: dict) -> list[dict]:
        """Подбор направлений с транспортом и климатом на указанный месяц."""
        filters = normalize_filters(filters or {})
        return await asyncio.to_thread(
            self.destinations.suggest_destinations, filters
        )

    async def get_destination(self, destination_id: str) -> dict | None:
        """Resolve a destination card by its catalog ID for explicit UI selection."""
        if not destination_id:
            return None
        return await asyncio.to_thread(
            lambda: next((item for item in self.provider.load_destinations()
                          if item.get("destination_id") == destination_id), None)
        )





    async def find_transport(self, filters: dict) -> list[dict]:

        filters = normalize_filters(filters or {})

        if not filters.get("date_from"):
            filters["date_from"] = datetime.now(timezone.utc).date().isoformat()
        errs = validate_transport_filters(filters)
        if errs:
            log.warning("find_transport: невалидные фильтры: %s", errs)
            return []
        return await asyncio.to_thread(self.transport.find_transport, filters)


    async def find_transfers(self, filters: dict) -> list[dict]:
        """
        Трансферы. Сегодня источника нет — вернёт [].
        Причина отдаётся через get_data_status()['transfers']['reason'].
        """
        filters = normalize_filters(filters or {})
        return await asyncio.to_thread(self.transfers.find_transfers, filters)


    async def get_climate(self, destination_id: str, month: int) -> dict | None:
        """Историческая среднемесячная справка по направлению (1..12)."""
        if not destination_id or not isinstance(month, int) or not (1 <= month <= 12):
            return None
        return await asyncio.to_thread(
            self.climate.get_climate, destination_id, month)

    async def get_weather(self, city_or_id: str, *, target_date: str | None = None,
                          month: int | None = None) -> dict | None:
        """Weather for a city: dated forecast if possible, otherwise labelled monthly normal."""
        if not city_or_id or (month is not None and not 1 <= month <= 12):
            return None
        normalized = normalize_city(city_or_id)
        destination = next((d for d in self.provider.load_destinations()
                            if d.get("destination_id") == city_or_id
                            or (normalize_city(d.get("name")) or "").casefold() == normalized.casefold()), None)
        if not destination:
            return None
        destination_id = destination["destination_id"]
        if month is not None:
            normal = await self.get_climate(destination_id, month)
            weather = ({"type": "climate_estimate", "target_month": month,
                        "expected_temp_c": normal["temp_mean_c"],
                        "precipitation_mean_mm_per_day": normal.get("precipitation_mean_mm_per_day"),
                        "source": normal.get("source"),
                        "note": "historical_monthly_average_not_forecast"}
                       if normal else None)
        else:
            try:
                days_ahead = ((date.fromisoformat(target_date) if target_date else self.climate.today())
                              - self.climate.today()).days
            except (TypeError, ValueError):
                return None
            weather = await asyncio.to_thread(self.climate.get_expected_weather,
                                              destination_id, days_ahead)
        return {"destination_id": destination_id, "city": destination.get("name"),
                "weather": weather} if weather else None

    async def get_forecast(self, destination_id: str, days: int = 3,
                           target_date: str | None = None) -> dict | None:
        """Direct forecast by destination ID, for callers using the package contract."""
        return await asyncio.to_thread(self.climate.get_forecast, destination_id,
                                       days, target_date)

    async def get_expected_weather(self, destination_id: str,
                                   days_ahead: int) -> dict | None:
        """Dated forecast or a labelled historical average for distant dates."""
        return await asyncio.to_thread(self.climate.get_expected_weather,
                                       destination_id, days_ahead)

    def _get_retriever(self):
        """
        Ленивое создание Retriever. Первый вызов может занять ~200ms на
        загрузку индекса; дальше всё в памяти процесса.

        Если модуль/индекс не готовы — вернёт объект Retriever с
        available=False, и его retrieve() даст [] без исключений.
        """
        if self._retriever is None:


            from .rag.retriever import Retriever

            index_dir = Path(os.getenv(
                "CATALOG_RAG_INDEX_DIR",
                str(PROJECT_ROOT / "data" / "vector_index"),
            ))
            self._retriever = Retriever(index_dir)
            log.info("RAG retriever инициализирован: available=%s, dir=%s",
                     self._retriever.available, index_dir)
        return self._retriever

    async def retrieve_descriptions(self, query: str, hotel_ids: list[str] | None = None,
                                    top_k: int = 5) -> list[dict]:
        """Semantic search over hotel metadata chunks, which are not reviews."""
        if not query or not query.strip():
            return []
        return await asyncio.to_thread(
            self._get_retriever().retrieve, query, hotel_ids or [], top_k
        )

    async def retrieve_reviews(self, query: str, hotel_ids: list[str],
                               top_k: int = 5) -> list[dict]:
        """No separate review corpus is provided; derived descriptions are never returned as reviews."""
        if not self.provider.load_reviews():
            return []


        log.info("Review source exists, but no review-specific index is configured")
        return []

    async def get_data_status(self) -> dict:
        """ Статус всех источников."""
        base = await asyncio.to_thread(self.provider.source_status)


        try:
            retriever = self._get_retriever()
            base["rag"] = {
                "available": retriever.available,
                "index_dir": str(retriever.store.index_dir),
                "chunks": retriever.store.manifest.get("chunks", 0),
                "model": retriever.store.manifest.get("embeddings_model", "unknown"),
                "reason": None if retriever.available
                else "index not built; run scripts/build_rag_index.py",
            }
        except Exception as exc:
            base["rag"] = {
                "available": False,
                "reason": f"retriever init failed: {exc}",
            }
        return base

    async def rag_status(self) -> dict:
        """ Узкий статус RAG без чтения остальных источников. Удобно для health-check эндпоинта №1. """
        try:
            retriever = self._get_retriever()
            return {
                "available": retriever.available,
                "index_dir": str(retriever.store.index_dir),
                "chunks": retriever.store.manifest.get("chunks", 0),
                "unique_hotels": retriever.store.manifest.get("unique_hotels", 0),
                "dim": retriever.store.manifest.get("dim", 0),
                "model": retriever.store.manifest.get("embeddings_model", "unknown"),
                "built_at": retriever.store.manifest.get("built_at"),
            }
        except Exception as exc:
            return {"available": False, "reason": f"retriever init failed: {exc}"}

_gateway: CatalogGateway | None = None
def get_catalog_gateway() -> CatalogGateway:
    global _gateway
    if _gateway is None:
        _gateway = CatalogGateway()
    return _gateway
