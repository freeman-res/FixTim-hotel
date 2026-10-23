#Валидация данных после нормализации.
from typing import Any
def validate_hotels(hotels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    #Оставляет только отели с hotel_id и непустым name.
    return [ h for h in hotels if h.get("hotel_id") is not None and h.get("name")]


def validate_offers(
    offers: list[dict[str, Any]],
    hotel_ids: set[int],) -> list[dict[str, Any]]:
    #Оставляет только offers, ссылающиеся на существующие отели.
    return [o for o in offers if o.get("hotel_id") in hotel_ids]


def validate_reviews(
    reviews: list[dict[str, Any]],
    hotel_ids: set[int],
) -> list[dict[str, Any]]:
    #Оставляет только reviews с существующим hotel_id и непустым text.
    return [r for r in reviews if r.get("hotel_id") in hotel_ids and r.get("text")]