"""Сопоставление фактических характеристик без выдуманных оценок."""
from ..schemas import CompareHotelsArgs


async def compare_hotels(args: CompareHotelsArgs, catalog) -> dict:
    hotels = await catalog.get_hotels_by_ids(args.hotel_ids)
    fields = ("hotel_id", "name", "city", "address", "location", "stars", "rating",
              "guest_rating", "total_price", "currency", "price", "price_estimate", "price_references",
              "record_kind", "booking_url",
              "availability", "amenities", "amenities_data", "description",
              "attractions", "facilities_text", "source", "source_details",
              "source_metrics", "data_quality", "is_demo")
    return {"hotels": [{field: hotel.get(field) for field in fields} for hotel in hotels],
            "preferences": args.preferences}
