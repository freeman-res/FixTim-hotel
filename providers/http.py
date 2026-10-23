"""Провайдер данных из API организаторов.
Скелет универсален. 
"""

from typing import Any

import httpx

from .base import BaseProvider


class HTTPProvider(BaseProvider):
    def __init__(self, base_url: str, headers: dict[str, str] | None = None):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}

    def _get(self, path: str, params: dict | None = None) -> list[dict[str, Any]]:
        resp = httpx.get(
            f"{self.base_url}{path}",
            params=params or {},
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        # Случай 1: список
        if isinstance(data, list):
            return data

        # Случай 2: словарь — найти первое значение-список
        if isinstance(data, dict):
            for value in data.values():
                if isinstance(value, list):
                    return value
            # Одна запись-словарь
            return [data]

        return []

    def load_hotels(self) -> list[dict[str, Any]]:
        return self._get("/hotels")

    def load_offers(self) -> list[dict[str, Any]]:
        return self._get("/offers")

    def load_reviews(self) -> list[dict[str, Any]]:
        return self._get("/reviews")