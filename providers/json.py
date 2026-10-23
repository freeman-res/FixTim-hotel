"""Провайдер данных из JSON-файлов.
Поддерживает два формата:
1. Файл — список объектов: [{"hotel_id": 1, ...}, ...]
2. Файл — словарь со списком внутри: {"hotels": [...]} или {"data": [...]}
Используется для демо-данных (через DemoProvider) и для реальных,
если организаторы дадут JSON."""
import json
from pathlib import Path
from typing import Any
from .providers.base import BaseProvider

class JSONProvider(BaseProvider):
    """Читает отели, offers и reviews из трёх JSON-файлов."""
    def __init__(self, hotels_path: str, offers_path: str, reviews_path: str):
        self.hotels_path = Path(hotels_path)
        self.offers_path = Path(offers_path)
        self.reviews_path = Path(reviews_path)
    @staticmethod
    def _read(path: Path) -> list[dict[str, Any]]:
        """ Читает JSON и возвращает список словарей.подерживает список, словарь со списком внутри и одну запись-словарь.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Случай 1: файл — список объектов
        if isinstance(data, list):
            return data
        # Случай 2: файл — словарь
        if isinstance(data, dict):
            # {"hotels": [...]} или {"data": [...]} — вернуть первый список
            for value in data.values():
                if isinstance(value, list):
                    return value
            # {"hotel_id": 1, ...} — одна запись
            return [data]
        return []
    def load_hotels(self) -> list[dict[str, Any]]:
        return self._read(self.hotels_path)
    def load_offers(self) -> list[dict[str, Any]]:
        return self._read(self.offers_path)
    def load_reviews(self) -> list[dict[str, Any]]:
        return self._read(self.reviews_path)