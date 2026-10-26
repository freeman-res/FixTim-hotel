"""Чтение JSON-файлов из data/demo/. Кэш по (путь + mtime): если файл не менялся — отдаём из памяти.
Это защищает find_offers на 32k отелях от повторного чтения на каждый запрос."""
from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Any
from .base import CatalogProvider
log = logging.getLogger(__name__)
class JsonProvider(CatalogProvider):
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        # Кэш: {имя_файла: (mtime, list[dict])}
        self._cache: dict[str, tuple[float, list[dict]]] = {}
    def _read(self, filename: str) -> list[dict]:
        path = self.data_dir / filename
        if not path.exists():
            return []
        mtime = path.stat().st_mtime
        cached = self._cache.get(filename)
        if cached and cached[0] == mtime:
            return cached[1]
        try:
            with path.open(encoding="utf-8") as f:
                data: Any = json.load(f)
            if not isinstance(data, list):
                log.error("%s: ожидался list, получено %s", filename, type(data).__name__)
                data = []
            self._cache[filename] = (mtime, data)
            return data
        except Exception as exc:  # noqa: BLE001
            log.error("Ошибка чтения %s: %s", filename, exc)
            return []
    def load_hotels(self) -> list[dict]:
        return self._read("hotels.json")
    def load_destinations(self) -> list[dict]:
        return self._read("destinations.json")
    def load_transport(self) -> list[dict]:
        return self._read("transport_options.json")
    def load_transfers(self) -> list[dict]:
        return self._read("transfer_options.json")
    def load_climate(self) -> list[dict]:
        return self._read("climate.json")
    def load_reviews(self) -> list[dict]:
        return self._read("reviews.json")
    def source_status(self) -> dict[str, dict]:
        """
        Для каждого ожидаемого файла — есть ли он.
        Это ключ к требованию ТЗ№3 п.4 ("понятная причина ограничения данных").
        """
        files = {"hotels": "hotels.json",
            "destinations": "destinations.json",
            "transport": "transport_options.json",
            "transfers": "transfer_options.json",
            "climate": "climate.json",
            "reviews": "reviews.json",}
        out: dict[str, dict] = {}
        for name, fname in files.items():
            p = self.data_dir / fname
            if p.exists():
                out[name] = {"available": True, "file": fname, "size_bytes": p.stat().st_size}
            else:
                out[name] = {"available": False, "reason": f"file {fname} not found"}
        return out