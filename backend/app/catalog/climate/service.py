"""
Климат и сезонность. Сегодня — источника нет.pytest tests/catalog -v
Пока источника нет — get_climate возвращает None,
а source_status() объясняет почему. Никогда не выдумываем погоду.
"""

from __future__ import annotations

import logging

from ..providers.base import CatalogProvider

log = logging.getLogger(__name__)


class ClimateService:
    def __init__(self, provider: CatalogProvider):
        self.provider = provider

    def get_climate(self, destination_id: str, month: int) -> dict | None:
        if not destination_id or not isinstance(month, int) or not (1 <= month <= 12):
            return None
        rows = self.provider.load_climate()
        if not rows:
            log.warning("get_climate: источник climate.json отсутствует — "
                        "возвращаю None")
            return None
        for r in rows:
            if r.get("destination_id") == destination_id and r.get("month") == month:
                return r
        return None