# Нормализация данных об отелях, предложениях и отзывах
from typing import Any
def _to_ini(value: Any) -> None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
def _to_float(value: Any) -> float|None:
    #Приводит значение к float.
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None    
def _to_str(value: Any ) -> bool|None:
    #Приводит значение к строке
    if value is None or value == "":
        return None
    text = str(value).strip()
    return text if text else None

def _to_bool(value: Any) -> bool|None:
    #приводит значение к bool
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value,str):
        lowered = value.strip().lower()
        if lowered in ("true", "1","yes", "да"):
            return True
        if lowered in ('false','0','no','нет'):
            return False
        return None
    if isinstance(value,(int, float)):
        return bool(value)
    return None

def _to_amenities(value: Any) -> list[str]:
    # Приводит к list
    if value is None:
        return[]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []
def normalize_hotel(raw: dict[str, Any]) -> dict[str, Any]:
#Приводит запись отеля к единой схеме.
    return {
        "hotel_id": _to_int(raw.get("hotel_id")),
        "name": _to_str(raw.get("name")),
        "city": _to_str(raw.get("city")),
        "price": _to_float(raw.get("price")),
        "rating": _to_float(raw.get("rating")),
        "amenities": _to_amenities(raw.get("amenities")),
        "description": _to_str(raw.get("description")),
        "location": _to_str(raw.get("location")),}
def normalize_offer(raw: dict[str, Any]) -> dict[str, Any]:
    #Приводит запись предложения к единой схеме.
    return {
        "offer_id": _to_int(raw.get("offer_id")),
        "hotel_id": _to_int(raw.get("hotel_id")),
        "check_in": _to_str(raw.get("check_in")),
        "check_out": _to_str(raw.get("check_out")),
        "guests": _to_int(raw.get("guests")),
        "total_price": _to_float(raw.get("total_price")),
        "available": _to_bool(raw.get("available")),
        "source": _to_str(raw.get("source")) or "unknown",}


def normalize_review(raw: dict[str, Any]) -> dict[str, Any]:
    #Приводит запись отзыва к единой схеме.
    return {
        "hotel_id": _to_int(raw.get("hotel_id")),
        "text": _to_str(raw.get("text")),
        "source": _to_str(raw.get("source")) or "unknown"}