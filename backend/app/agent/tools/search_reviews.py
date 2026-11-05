from ..schemas import SearchReviewsArgs


async def search_reviews(args: SearchReviewsArgs, catalog) -> dict:
    matches = await catalog.retrieve_reviews(args.query, args.hotel_ids, args.top_k)
    valid_ids = set(map(str, args.hotel_ids))

    matches = [match for match in matches
               if isinstance(match, dict) and str(match.get("hotel_id")) in valid_ids and match.get("source")]
    return {"matches": matches[:args.top_k], "count": min(args.top_k, len(matches))}
