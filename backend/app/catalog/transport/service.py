"""ТЗ№3 п.7: "единый поиск авиа-, ЖД- и автобусных вариантов,
приведение расписаний к общей схеме".
Формат уже общий: импортёр сделал TransportOption с type-дискриминатором.
Здесь только фильтрация + сортировка."""
from __future__ import annotations
import logging
from ..providers.base import CatalogProvider
from ..search.exact import filter_transport
log = logging.getLogger(__name__)
class TransportService:
    def __init__(self, provider: CatalogProvider):
        self.provider = provider
    def find_transport(self, filters: dict) -> list[dict]:
        filters = filters or {}
        options = self.provider.load_transport()
        matched = filter_transport(options, filters)
        # Сортировка: сначала по цене (дешёвые первыми), потом по времени.
        # Записи без цены — в конце (агент №2 так и должен их показывать:
        # "цена не найдена").
        def sort_key(t: dict):
            p = (t.get("price") or {}).get("amount_min_rub")
            dep = t.get("departure_utc") or t.get("schedule_date") or ""
            return (p is None, p or 0, dep)
        matched.sort(key=sort_key)
        log.info("find_transport: %d из %d вариантов после фильтров",
                 len(matched), len(options))
        return matched