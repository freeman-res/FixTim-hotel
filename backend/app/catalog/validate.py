"""Валидация входных фильтров и исходящих записей.
ТЗ№3 п.6: методы должны возвращать записи с исходными ID и корректными
типами данных. Здесь — проверки до и после обработки."""

from __future__ import annotations
# Обязательные поля любой записи-предложения (ТЗ№3 п.3.5)
REQUIRED_OFFER_FIELDS = (
    "hotel_id",      # или transport_id / destination_id
    "source",        # dict с source.name, source.type, source.retrieved_at
    "is_demo",       ) # bool
REQUIRED_SOURCE_FIELDS = ("name", "type", "retrieved_at")
def validate_offer_filters(filters: dict) -> list[str]:
    """ Возвращает список ошибок (пустой — значит ок).
    Пример: ["stars_min должен быть int, получено str"],
    ["hotel_ids должен быть list"] """
    errors: list[str] = []
    if not isinstance(filters, dict):
        return [f"filters должен быть dict, получено {type(filters).__name__}"]
    if "hotel_ids" in filters and not isinstance(filters["hotel_ids"], list):
        errors.append("hotel_ids должен быть list")
    for k in ("stars_min", "stars_max", "price_max", "price_min"):
        if k in filters:
            try:
                int(filters[k])
            except (TypeError, ValueError):
                errors.append(f"{k} должен быть числом, получено {filters[k]!r}")
    if "check_in" in filters and "check_out" in filters:
        if filters["check_in"] and filters["check_out"]:
            if filters["check_in"] > filters["check_out"]:
                errors.append("check_in позже check_out")
    if "require_price" in filters and not isinstance(filters["require_price"], bool):
        errors.append("require_price должен быть bool")
    return errors

def validate_transport_filters(filters: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(filters, dict):
        return [f"filters должен быть dict, получено {type(filters).__name__}"]
    allowed_types = {"plane", "bus", "train", None}
    t = filters.get("type")
    if t not in allowed_types:
        errors.append(f"type должен быть одним из {allowed_types}, получено {t!r}")
    if "max_price" in filters:
        try:
            int(filters["max_price"])
        except (TypeError, ValueError):
            errors.append("max_price должен быть числом")
    return errors
def validate_record(record: dict, required: tuple[str, ...]) -> list[str]:
    """Проверяет, что в записи есть обязательные поля и source корректен.Используется в sanity-check внутри сервисов. """
    errors: list[str] = []
    for f in required:
        if f not in record or record[f] is None:
            errors.append(f"missing field: {f}")
    src = record.get("source")
    if not isinstance(src, dict):
        errors.append("source должен быть dict")
    else:
        for f in REQUIRED_SOURCE_FIELDS:
            if f not in src:
                errors.append(f"source.{f} отсутствует")
    return errors