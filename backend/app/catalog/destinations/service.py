"""Подбор направлений. ТЗ№3 п.7.
Возвращает города, обогащённые:
    - transport_available: какие типы транспорта связывают origin → destination
    - min_transport_price_rub: минимум по найденным вариантам (или None)
    - climate: None + reason (нет источника климата)
    - source, is_demo — как везде
Не решает "какое направление лучше" — это делает №2."""
from __future__ import annotations
import logging
from ..providers.base import CatalogProvider
from ..search.exact import filter_destinations
log = logging.getLogger(__name__)
def _transport_summary(transport: list[dict], origin_city: str | None,
                       destination_city: str) -> dict:
    """Смотрит, какие рейсы/автобусы из origin_city идут в destination_city.
    Возвращает агрегат: типы транспорта + минимальная цена (если есть). """
    types: set[str] = set()
    min_price: int | None = None
    for t in transport:
        if (t.get("to") or {}).get("city") != destination_city:
            continue
        if origin_city and (t.get("from") or {}).get("city") != origin_city:
            continue
        types.add(t.get("type") or "unknown")
        price = (t.get("price") or {})
        amount = price.get("amount_min_rub") or price.get("amount_min")
        if amount is not None and (min_price is None or amount < min_price):
            min_price = amount
    return {
        "available": bool(types),
        "types": sorted(types),
        "min_transport_price_rub": min_price,
        "min_transport_price_note": (
            "route_level_range" if min_price is not None else None ),}
class DestinationsService:
    def __init__(self, provider: CatalogProvider):
        self.provider = provider
    def suggest_destinations(self, filters: dict) -> list[dict]:
        filters = filters or {}
        destinations = self.provider.load_destinations()
        matched = filter_destinations(destinations, filters)
        # Origin нужен, чтобы показать "как добраться"
        origin_city = filters.get("origin_city")
        transport = self.provider.load_transport()
        source_status = self.provider.source_status()
        enriched: list[dict] = []
        for d in matched:
            d2 = dict(d)  # копия, чтобы не мутировать кэш провайдера
            d2["transport_available"] = _transport_summary(
                transport, origin_city, d["name"]
            )
            # climate честно None + reason, если источника нет.
            # Если фильтр по месяцу задан, но источника нет —
            # не отсекаем направление (иначе останемся с пустым списком).
            if source_status["climate"]["available"]:
                d2["climate"] = None  # TODO: подключить, когда будет источник
            else:
                d2["climate"] = {
                    "status": "unknown",
                    "reason": source_status["climate"]["reason"],
                }
            enriched.append(d2)
        # Сортировка: сначала те, куда есть транспорт (агент №2 часто
        # хочет показать «реалистичные» варианты первыми).
        enriched.sort(key=lambda x: (
            not x["transport_available"]["available"],
            x.get("name") or "",
        ))
        log.info("suggest_destinations: %d из %d после фильтров",
                 len(enriched), len(destinations))
        return enriched