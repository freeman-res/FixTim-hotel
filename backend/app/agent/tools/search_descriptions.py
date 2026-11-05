"""Semantic retrieval over sourced hotel descriptions, never over reviews."""

from ..schemas import SearchHotelDescriptionsArgs


async def search_hotel_descriptions(args: SearchHotelDescriptionsArgs, catalog) -> dict:
    matches = await catalog.retrieve_descriptions(args.query, args.hotel_ids, args.top_k)
    return {"matches": matches[:args.top_k], "count": min(len(matches), args.top_k),
            "content_type": "derived_hotel_metadata_not_reviews"}
