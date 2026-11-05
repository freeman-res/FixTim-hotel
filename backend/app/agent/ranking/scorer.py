"""Жёсткая фильтрация и воспроизводимое ранжирование предложений."""
from typing import Any
import math
from datetime import date

from ...catalog.normalize import normalize_city

DEFAULT_WEIGHTS = {"price": 0.25, "rating": 0.20, "amenities": 0.15, "location": 0.15, "semantic": 0.25}


def _float(value: Any) -> float | None:
    try:
        result = float(value) if value is not None else None
        return result if result is not None and math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def rank_offers(
    offers: list[dict], filters: dict, preferences: list[str],
    rejected_hotel_ids: set[str], limit: int = 5, weights: dict | None = None,
) -> list[dict]:
    """Нет данных о требуемом удобстве/цене -> нельзя считать условие выполненным."""
    weights = weights or DEFAULT_WEIGHTS
    eligible = []
    required = {str(x).lower() for x in filters.get("required_amenities", [])}
    max_price = _float(filters.get("max_total_price"))
    city = str(normalize_city(filters.get("city")) or "").casefold()
    currency = str(filters.get("currency") or "").strip().casefold()
    try:
        nights = max(1, (date.fromisoformat(filters["check_out"]) - date.fromisoformat(filters["check_in"])).days)
    except (KeyError, TypeError, ValueError):
        nights = None

    for candidate in offers:
        if not isinstance(candidate, dict) or candidate.get("hotel_id") is None:
            continue
        if str(candidate["hotel_id"]) in rejected_hotel_ids:
            continue
        location = candidate.get("location") or {}
        located_city = location.get("city") if isinstance(location, dict) else None
        candidate_city = str(normalize_city(candidate.get("city") or located_city) or "").casefold()
        if city and candidate_city and candidate_city != city:
            continue
        if city and not candidate_city and not candidate.get("catalog_city_filter_applied"):
            continue
        candidate_currency = str(candidate.get("currency") or "").strip().casefold()
        if currency and candidate_currency and candidate_currency != currency:
            continue
        amenities = {str(x).lower() for x in (candidate.get("amenities") or [])}
        if not required.issubset(amenities):
            continue
        price = _float(candidate.get("total_price"))
        estimate_data = candidate.get("price_estimate") or {}
        estimated_nightly = (_float(estimate_data.get("amount_rub"))
                             if estimate_data.get("currency") == "RUB"
                             and estimate_data.get("unit") == "per_night" else None)
        estimated_total = estimated_nightly * nights if estimated_nightly is not None and nights else None
        if max_price is not None and price is not None and price > max_price:
            continue


        rating = _float(candidate.get("rating"))
        semantic = _float(candidate.get("semantic_score"))
        location = _float(candidate.get("location_score"))
        price_score = max(0.0, min(1.0, 1 - price / max_price)) if price is not None and max_price else 0.0
        if price is None and max_price and estimated_total is not None:
            price_score = 0.5 * max(0.0, min(1.0, 1 - estimated_total / max_price))
        rating_score = max(0.0, min(1.0, rating / 5)) if rating is not None else 0.0
        amenity_score = len(amenities.intersection({p.lower() for p in preferences})) / max(1, len(preferences))
        semantic_score = max(0.0, min(1.0, semantic)) if semantic is not None else 0.0
        location_score = max(0.0, min(1.0, location)) if location is not None else 0.0
        score = (
            weights["price"] * price_score + weights["rating"] * rating_score +
            weights["amenities"] * amenity_score + weights["location"] * location_score +
            weights["semantic"] * semantic_score
        )
        reasons = []
        if required:
            reasons.append("Есть обязательные удобства: " + ", ".join(sorted(required)))
        if max_price is not None and price is not None:
            reasons.append("Стоимость укладывается в бюджет")
        elif max_price is not None and price is None:
            reasons.append("Цена не указана; соответствие бюджету не подтверждено")
        if price is None and estimated_nightly is not None:
            reasons.append(f"Примерно {estimated_nightly:g} ₽/ночь по средним данным; наличие и тариф не подтверждены")
        if currency and not candidate_currency:
            reasons.append("Валюта цены не указана")
        if rating is not None:
            reasons.append(f"Рейтинг {rating:g}/5")
        if location_score > 0:
            reasons.append("Расположение соответствует запросу (оценка источника)")
        if semantic_score > 0:
            reasons.append("Описание соответствует пожеланиям (оценка источника)")
        item = dict(candidate)
        item["match_score"] = round(score, 4)
        item["reason"] = "; ".join(reasons) if reasons else "Соответствует заданным фильтрам"
        eligible.append(item)
    eligible.sort(key=lambda x: (
        -x["match_score"],
        x.get("total_price") is None,
        _float((x.get("price_estimate") or {}).get("amount_rub")) or float("inf"),
        str(x["hotel_id"]),
    ))
    return eligible[:limit]
