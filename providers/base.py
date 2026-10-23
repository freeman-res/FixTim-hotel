"""Базовый интерфейс провайдера данных об отелях.
Все провайдеры (json, csv, sql, http, demo) наследуются от BaseProvider
и реализуют три метода: load_hotels, load_offers, load_reviews.
CatalogService работает только с этим интерфейсом и не знает,
откуда именно пришли данные.
"""
from abc import ABC, abstractmethod
from typing import Any
class BaseProvider(ABC):
    """Абстрактный провайдер данных."""
    @abstractmethod
    def load_hotels(self) -> list[dict[str, Any]]:
        """Возвращает список сырых словарей об отелях."""
        ...
    @abstractmethod
    def load_offers(self) -> list[dict[str, Any]]:
        """Возвращает список сырых словарей о предложениях."""
        ...
    @abstractmethod
    def load_reviews(self) -> list[dict[str, Any]]:
        """Возвращает список сырых словарей об отзывах."""
        ...
        