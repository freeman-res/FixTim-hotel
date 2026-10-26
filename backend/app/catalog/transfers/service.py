
"""Трансферы. Причина отдаётся через source_status()
агент №2 сам решит, показать ли её пользователю."""
from __future__ import annotations

import logging

from ..providers.base import CatalogProvider

log = logging.getLogger(__name__)


class TransfersService:
    def __init__(self, provider: CatalogProvider):
        self.provider = provider

    def find_transfers(self, filters: dict) -> list[dict]:
        items = self.provider.load_transfers()
        if not items:
            log.warning("find_transfers: источник transfer_options.json отсутствует "
                        "или пуст — возвращаю []")
            return []
        # Фильтрация аналогична find_transport — оставляю простую версию.
        from_city = (filters or {}).get("from_city")
        to_city   = (filters or {}).get("to_city")
        out = []
        for t in items:
            if from_city and (t.get("from") or {}).get("city") != from_city:
                continue
            if to_city and (t.get("to") or {}).get("city") != to_city:
                continue
            out.append(t)
        return out