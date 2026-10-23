"""
Провайдер данных из CSV-файлов.

Используется, если организаторы дадут CSV.
На хакатоне:
    make_provider("csv",
                  hotels_csv="path/to/hotels.csv",
                  offers_csv="path/to/offers.csv",
                  reviews_csv="path/to/reviews.csv")
"""

from typing import Any

import pandas as pd

from .providers.base import BaseProvider


class CSVProvider(BaseProvider):
    def __init__(
        self,
        hotels_csv: str,
        offers_csv: str | None = None,
        reviews_csv: str | None = None,
    ):
        self.hotels_csv = hotels_csv
        self.offers_csv = offers_csv
        self.reviews_csv = reviews_csv

    @staticmethod
    def _read(path: str) -> list[dict[str, Any]]:
        # sep=None + engine="python" — автоопределение разделителя (запятая, ;, \t)
        df = pd.read_csv(path, sep=None, engine="python")
        return df.to_dict(orient="records")

    def load_hotels(self) -> list[dict[str, Any]]:
        return self._read(self.hotels_csv)

    def load_offers(self) -> list[dict[str, Any]]:
        return self._read(self.offers_csv) if self.offers_csv else []

    def load_reviews(self) -> list[dict[str, Any]]:
        return self._read(self.reviews_csv) if self.reviews_csv else []