"""Weather lookup through the catalog gateway, with explicit source labeling."""
from ..schemas import WeatherArgs


async def get_weather(args: WeatherArgs, catalog, state: dict) -> dict:
    trip = state.get("trip") or {}
    city_or_id = args.destination_id or args.city or trip.get("destination_id") or trip.get("city")
    if not city_or_id:
        return {"outcome": "clarification", "message": "Для какого города узнать погоду?"}
    result = await catalog.get_weather(city_or_id,
                                       target_date=args.target_date,
                                       month=args.month)
    if not result:
        return {"outcome": "unavailable", "message": "Данные о погоде для этого города и периода недоступны."}
    return {"outcome": "results", **result}
