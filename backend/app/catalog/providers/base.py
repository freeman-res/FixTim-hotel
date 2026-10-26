"""Абстрактный интерфейс источника данных.
ТЗ№3 п.2.2: providers/base.py — общий интерфейс.
Любой новый источник (csv.py, http.py, sql.py) реализует этот ABC."""
from __future__ import annotations
from abc import ABC, abstractmethod
class CatalogProvider(ABC):
    """ Все методы синхронные — это чтение файла/БД. Async обёртка (asyncio.to_thread) — на уровне фасада catalog/service.py."""
    @abstractmethod
    def load_hotels(self) -> list[dict]: ...
    @abstractmethod
    def load_destinations(self) -> list[dict]: ...
    @abstractmethod
    def load_transport(self) -> list[dict]: ...
    @abstractmethod
    def load_transfers(self) -> list[dict]: ...
    @abstractmethod
    def load_climate(self) -> list[dict]: ...
    @abstractmethod
    def load_reviews(self) -> list[dict]: ...
    @abstractmethod
    def source_status(self) -> dict[str, dict]:
        """
        Метаданные о доступности источников.
        Например: {"transfers": {"available": False, "reason": "no file"}}
        Нужно для ТЗ№3 п.4: "понятная причина ограничения данных".
        """