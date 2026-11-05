from ..ranking.scorer import rank_offers
from ..schemas import SearchHotelsArgs
from ...catalog.normalize import normalize_filters


async def search_hotels(args: SearchHotelsArgs, catalog, state: dict) -> dict:

    filters = args.filters.model_dump(exclude_none=True)
    trip = state.get("trip", {})
    for key in ("city", "check_in", "check_out", "guests", "max_total_price", "currency", "required_amenities"):
        if trip.get(key) is not None:
            filters[key] = trip[key]
    if trip.get("adults") is not None:
        filters["adults"] = trip["adults"]
    filters = normalize_filters(filters)
    preferences = list(trip.get("preferences") or args.preferences)
    result = await catalog.find_offers(filters)
    offers = result.get("offers", []) if isinstance(result, dict) else result
    if not isinstance(offers, list):
        raise ValueError("Каталог должен возвращать список предложений")
    hotels = rank_offers(offers, filters, preferences, set(map(str, state.get("rejected_hotel_ids", []))), args.limit)
    warnings = []
    if any(h.get("price_estimate") for h in hotels):
        warnings.append("Примерная цена отеля рассчитана по средним данным; наличие номера и итоговая стоимость не подтверждены.")
    if any(h.get("record_kind") == "live_offer" for h in hotels):
        warnings.append("Цена получена из поиска Туту; проверьте итоговую сумму и наличие номера перед бронированием.")
    return {"hotels": hotels, "count": len(hotels), "filters": filters, "warnings": warnings}
