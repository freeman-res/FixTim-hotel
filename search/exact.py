from typing import Any
import pandas as pd
from contracts.hotel import Hotel, Offer
class ExactSearch:
    #Структурированный поиск по отелям и предложениям."""

    def __init__(
        self,
        hotels: list[dict[str, Any]],
        offers: list[dict[str, Any]],
    ):
        self.hotels = pd.DataFrame(hotels)
        self.offers = pd.DataFrame(offers)
# Внутренние фильтры
    def _apply_hotel_filters(self, df: pd.DataFrame, filters: dict[str, Any] ) -> pd.DataFrame:
        """Фильтры, относящиеся к самому отелю: city, rating_min, price_max, amenities.
        None и пустые значения не фильтруют — пропускаем."""
        if filters.get("city"):
            df = df[df["city"] == filters["city"]]
        if filters.get("rating_min") is not None:
            df = df[df["rating"] >= filters["rating_min"]]
        if filters.get("price_max") is not None and "price" in df.columns:
            df = df[df["price"] <= filters["price_max"]]
        if filters.get("amenities"):
            for amenity in filters["amenities"]:
                df = df[df["amenities"].apply(
                        lambda x, a=amenity: a in (x if isinstance(x, list) else []))]
        return df

    def _apply_offer_filters(
        self, df: pd.DataFrame, filters: dict[str, Any] ) -> pd.DataFrame:
        """
        Фильтры, относящиеся к предложению: check_in, check_out, guests, total_price.
        """
        if filters.get("check_in") and "check_in" in df.columns:
            df = df[df["check_in"] >= filters["check_in"]]

        if filters.get("check_out") and "check_out" in df.columns:
            df = df[df["check_out"] <= filters["check_out"]]

        if filters.get("guests") is not None and "guests" in df.columns:
            df = df[df["guests"] >= filters["guests"]]

        if filters.get("price_max") is not None and "total_price" in df.columns:
            df = df[df["total_price"] <= filters["price_max"]]

        return df

    # Публичные функции пунт 6 ТЗ — интерфейс для AI-агента


    async def find_offers(self, filters: dict[str, Any]) -> list[Offer]:
        """
        Поиск предложений по точным параметрам.
        Возвращает [] если ничего не найдено или данные пусты.
        available=None сохраняется как None — не превращается в False.
        """
        if self.offers.empty or self.hotels.empty:
            return []

        # Соединяем offers с hotels по hotel_id, чтобы фильтровать по полям отеля
        merged = self.offers.merge(
            self.hotels,
            on="hotel_id",
            how="left",
            suffixes=("", "_hotel"),
        )

        merged = self._apply_hotel_filters(merged, filters)
        merged = self._apply_offer_filters(merged, filters)

        if merged.empty:
            return []

        return [Offer(**self._clean_offer(row)) for row in merged.to_dict(orient="records")]

    async def get_hotel(self, hotel_id: int) -> Hotel | None:
        #Возвращает отель по hotel_id или None, если не найден.
        if self.hotels.empty:
            return None

        row = self.hotels[self.hotels["hotel_id"] == hotel_id]
        if row.empty:
            return None

        return Hotel(**self._clean_hotel(row.iloc[0].to_dict()))

    async def get_hotels_by_ids(self, hotel_ids: list[int]) -> list[Hotel]:
        #Возвращает список отелей по списку hotel_ids. Отсутствующие — пропускает.
        if not hotel_ids or self.hotels.empty:
            return []

        rows = self.hotels[self.hotels["hotel_id"].isin(hotel_ids)]
        return [Hotel(**self._clean_hotel(r)) for r in rows.to_dict(orient="records")]
# Приведение pandas-типов к JSON-совместимым (Pydantic)

    @staticmethod
    def _clean_hotel(record: dict[str, Any]) -> dict[str, Any]:
        """
        Убирает NaN из pandas: NaN → None.
        Убирает поля, которых нет в Hotel (например, лишние колонки после merge).
        """
        cleaned = {}
        for key, value in record.items():
            if isinstance(value, float) and pd.isna(value):
                cleaned[key] = None
            else:
                cleaned[key] = value

        # Оставляем только поля модели Hotel — на случай, если после merge
        # в словаре оказались лишние колонки
        allowed = {"hotel_id", "name", "city", "price", "rating",
                   "amenities", "description", "location"}
        return {k: v for k, v in cleaned.items() if k in allowed}

    @staticmethod
    def _clean_offer(record: dict[str, Any]) -> dict[str, Any]:
        #Для Offer — аналогично. available=None сохраняется как None.
        cleaned = {}
        for key, value in record.items():
            if isinstance(value, float) and pd.isna(value):
                cleaned[key] = None
            else:
                cleaned[key] = value
        allowed = {"offer_id", "hotel_id", "check_in", "check_out",
                   "guests", "total_price", "available", "source"}
        result = {k: v for k, v in cleaned.items() if k in allowed}

        # приводим к питоновским типам для Pydantic
        if result.get("total_price") is not None:
            result["total_price"] = float(result["total_price"])
        if result.get("guests") is not None:
            result["guests"] = int(result["guests"])
        if result.get("offer_id") is not None:
            result["offer_id"] = int(result["offer_id"])
        if result.get("hotel_id") is not None:
            result["hotel_id"] = int(result["hotel_id"])

        return result