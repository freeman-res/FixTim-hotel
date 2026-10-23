"""
Провайдер данных из SQLite.

Используется, если организаторы дадут SQLite-базу.
На хакатоне:
    make_provider("sql",
                  db_path="path/to/db.sqlite",
                  hotels_table="hotels",
                  offers_table="offers",
                  reviews_table="reviews")
"""

import sqlite3
from typing import Any

import pandas as pd

from .base import BaseProvider


class SQLProvider(BaseProvider):
    def __init__(
        self,
        db_path: str,
        hotels_table: str = "hotels",
        offers_table: str = "offers",
        reviews_table: str = "reviews",
    ):
        self.db_path = db_path
        self.hotels_table = hotels_table
        self.offers_table = offers_table
        self.reviews_table = reviews_table

    def _read(self, table: str) -> list[dict[str, Any]]:
        con = sqlite3.connect(self.db_path)
        try:
            df = pd.read_sql(f"SELECT * FROM {table}", con)
            return df.to_dict(orient="records")
        finally:
            con.close()

    def load_hotels(self) -> list[dict[str, Any]]:
        return self._read(self.hotels_table)

    def load_offers(self) -> list[dict[str, Any]]:
        return self._read(self.offers_table)

    def load_reviews(self) -> list[dict[str, Any]]:
        return self._read(self.reviews_table)