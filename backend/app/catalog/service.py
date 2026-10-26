from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from .climate.service import ClimateService
from .destinations.service import DestinationsService
from .hotels.service import HotelsService
from .normalize import normalize_filters
from .providers.factory import get_provider
from .transport.service import TransportService
from .transfers.service import TransfersService
from .validate import (
    validate_offer_filters,
    validate_transport_filters,
)

log = logging.getLogger(__name__)

# Корень проекта (backend/app/catalog/service.py → parents[3])
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class CatalogGateway:
    """
    Единственная точка входа для №2.
    Никаких прямых обращений к провайдеру извне этого класса —
    это фиксирует архитектуру (ТЗ№3 п.2.1).
    """

    def __init__(self, provider=None):
        # Провайдер: по умолчанию JsonProvider через factory,
        # в тестах можно передать свой (см. tests/catalog/).
        self.provider = provider or get_provider()

        # Под-сервисы — синхронные, носят чистую логику без I/O.
        # Async-обёрткой занимается сам фасад.
        self.hotels       = HotelsService(self.provider)
        self.destinations = DestinationsService(self.provider)
        self.transport    = TransportService(self.provider)
        self.transfers    = TransfersService(self.provider)
        self.climate      = ClimateService(self.provider)

        # Ленивая инициализация RAG — не грузим индекс, пока не понадобится.
        self._retriever = None


# ОТЕЛИ


    async def find_offers(self, filters: dict) -> list[dict]:
        """
        Структурированный поиск отелей.

        Фильтры (поддерживаемые): city, hotel_ids, stars_min, stars_max,
        price_min, price_max, amenities (dict), + любые, которые
        понимает search/exact.filter_hotels.

        Возвращает [] при невалидных фильтрах — НЕ бросает исключение,
        чтобы агент №2 мог показать пользователю понятный ответ
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


    # НАПРАВЛЕНИЯ  

    async def suggest_destinations(self, filters: dict) -> list[dict]:
        """Подбор направлений. Каждое направление обогащено transport_available
        и climate пока нет источника        """
        filters = normalize_filters(filters or {})
        return await asyncio.to_thread(
            self.destinations.suggest_destinations, filters
        )


    # ТРАНСПОРТ  (ТЗ№3 п.6: find_transport)


    async def find_transport(self, filters: dict) -> list[dict]:
#Единый поиск по самолётам/автобусам/поездам.
       
        filters = normalize_filters(filters or {})
        errs = validate_transport_filters(filters)
        if errs:
            log.warning("find_transport: невалидные фильтры: %s", errs)
            return []
        return await asyncio.to_thread(self.transport.find_transport, filters)
 # ТРАНСФЕРЫ

    async def find_transfers(self, filters: dict) -> list[dict]:
        """
        Трансферы. Сегодня источника нет — вернёт [].
        Причина отдаётся через get_data_status()['transfers']['reason'].
        """
        filters = normalize_filters(filters or {})
        return await asyncio.to_thread(self.transfers.find_transfers, filters)
# КЛИМАТ

    async def get_climate(self, destination_id: str, month: int) -> dict | None:
        """
        Сезонная справка по направлению на конкретный месяц (1..12).
        Сегодня источника нет — вернёт None.
        Причина отдаётся через get_data_status()['climate']['reason'].
        """
        if not destination_id or not isinstance(month, int) or not (1 <= month <= 12):
            return None
        return await asyncio.to_thread(
            self.climate.get_climate, destination_id, month)
 # RAG
    def _get_retriever(self):
        """
        Ленивое создание Retriever. Первый вызов может занять ~200ms на
        загрузку индекса; дальше всё в памяти процесса.

        Если модуль/индекс не готовы — вернёт объект Retriever с
        available=False, и его retrieve() даст [] без исключений.
        """
        if self._retriever is None:
            # Импорт внутри метода — чтобы import service.py не требовал
            # наличия faiss/numpy-индекса (он нужен только при вызове RAG).
            from .rag.retriever import Retriever

            index_dir = Path(os.getenv(
                "CATALOG_RAG_INDEX_DIR",
                str(PROJECT_ROOT / "data" / "vector_index"),
            ))
            self._retriever = Retriever(index_dir)
            log.info("RAG retriever инициализирован: available=%s, dir=%s",
                     self._retriever.available, index_dir)
        return self._retriever

    async def retrieve_reviews(self, query: str, hotel_ids: list[str],
                               top_k: int = 5) -> list[dict]:
        """
        Семантический поиск фрагментов, ЖЁСТКО привязанных к hotel_ids."""
        if not query or not query.strip():
            return []
        return await asyncio.to_thread(
            self._get_retriever().retrieve, query, hotel_ids or [], top_k
        )
    # ДИАГНОСТИКА
    async def get_data_status(self) -> dict:
        """ Статус всех источников."""
        base = await asyncio.to_thread(self.provider.source_status)
        # Добавляем статус RAG — он не является «источником» в том же смысле,
        # но по факту это тоже зависимость (embeddings №2 + построенный индекс).
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
        except Exception as exc:  # noqa: BLE001 — диагностика не должна падать
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
        except Exception as exc:  # noqa: BLE001
            return {"available": False, "reason": f"retriever init failed: {exc}"}

_gateway: CatalogGateway | None = None
def get_catalog_gateway() -> CatalogGateway:
    global _gateway
    if _gateway is None:
        _gateway = CatalogGateway()
    return _gateway