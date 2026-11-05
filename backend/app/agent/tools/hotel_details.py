from ..schemas import HotelDetailsArgs


async def get_hotel_details(args: HotelDetailsArgs, catalog) -> dict:
    hotel = await catalog.get_hotel(args.hotel_id)
    return {"hotel": hotel, "found": hotel is not None}
