from .registry import ToolRegistry, RegisteredTool
from ..schemas import (SearchHotelsArgs, HotelDetailsArgs, SearchReviewsArgs,
                       CompareHotelsArgs, SearchTransportArgs, SearchHotelDescriptionsArgs,
                       WeatherArgs)
from .search_hotels import search_hotels
from .hotel_details import get_hotel_details
from .search_reviews import search_reviews
from .compare_hotels import compare_hotels
from .search_transport import search_transport
from .search_descriptions import search_hotel_descriptions
from .weather import get_weather


def build_registry(catalog, state: dict) -> ToolRegistry:
    registry = ToolRegistry()

    async def search(args):
        return await search_hotels(args, catalog, state)

    async def details(args):
        return await get_hotel_details(args, catalog)

    async def reviews(args):
        return await search_reviews(args, catalog)

    async def compare(args):
        return await compare_hotels(args, catalog)

    async def transport(args):
        return await search_transport(args, catalog, state)

    async def descriptions(args):
        return await search_hotel_descriptions(args, catalog)

    async def weather(args):
        return await get_weather(args, catalog, state)

    registry.register(RegisteredTool("search_hotels", "Найти отели по фильтрам. Сначала ищем датированные предложения Туту, при отсутствии — каталог с price_estimate. price_estimate является синтетической приблизительной ценой за ночь, не подтверждает доступность или бюджет. price_references — исторические справочные суммы; это не актуальная цена. Для бюджета используй только проверенные price/total_price.", SearchHotelsArgs, search))
    registry.register(RegisteredTool("get_hotel_details", "Получить реальные сведения об одном отеле", HotelDetailsArgs, details))
    registry.register(RegisteredTool("search_reviews", "Семантически найти отзывы по указанным отелям", SearchReviewsArgs, reviews))
    registry.register(RegisteredTool("compare_hotels", "Сравнить характеристики отелей. price_references — справочные суммы из датасета с неизвестной валютой и условиями, это не актуальная цена и не предложение для бронирования. guest_rating может быть по неизвестной шкале; не сравнивай его как подтверждённую оценку из 5.", CompareHotelsArgs, compare))
    registry.register(RegisteredTool("search_transport", "Найти транспорт по направлению и дате. Авиа и поезда сначала ищутся через Туту. При отсутствии авиабилетов возвращается только price_estimate маршрута: это не рейс, без расписания и бронирования. Для поездов запасной источник РЖД. Не называй неподтверждённые варианты доступными к покупке.", SearchTransportArgs, transport, timeout_seconds=50))
    registry.register(RegisteredTool("search_hotel_descriptions", "Семантически искать по описанию и характеристикам отелей. Это производный текст из каталога, НЕ отзывы; не выдавай его за опыт туристов и не делай выводов о цене или доступности.", SearchHotelDescriptionsArgs, descriptions))
    registry.register(RegisteredTool("get_weather", "Получить прогноз погоды на дату до 16 дней либо историческую среднемесячную температуру для дальнего периода. Климатическая средняя не является прогнозом на конкретный день.", WeatherArgs, weather))
    return registry
