"""
Контракт CatalogGateway с агентом №2 (ТЗ№3 п.6).
"""
import inspect
import pytest
from backend.app.catalog.service import CatalogGateway
REQUIRED_ASYNC_METHODS = [
    "find_offers",
    "get_hotel",
    "get_hotels_by_ids",
    "retrieve_reviews",
    "suggest_destinations",
    "find_transport",
    "find_transfers",
    "get_climate"]


@pytest.mark.parametrize("method_name", REQUIRED_ASYNC_METHODS)
def test_method_exists_and_is_async(method_name):
    """Если кто-то случайно сделает метод sync — №2 сломает await."""
    assert hasattr(CatalogGateway, method_name), \
        f"CatalogGateway.{method_name} отсутствует — нарушен контракт №2"
    method = getattr(CatalogGateway, method_name)
    assert inspect.iscoroutinefunction(method), \
        f"{method_name} должен быть async def"
@pytest.mark.asyncio
async def test_find_offers_returns_list(gateway):
    result = await gateway.find_offers({})
    assert isinstance(result, list)
    assert len(result) == 3
@pytest.mark.asyncio
async def test_get_hotel_returns_dict_or_none(gateway):
    found = await gateway.get_hotel("hotel_t_001")
    assert isinstance(found, dict)
    assert found["hotel_id"] == "hotel_t_001"
    assert await gateway.get_hotel("nonexistent") is None
    assert await gateway.get_hotel("") is None
@pytest.mark.asyncio
async def test_get_hotels_by_ids_preserves_order(gateway):
    """Порядок результата = порядок переданных ID (предсказуемо для №2)."""
    ids = ["hotel_t_003", "hotel_t_001"]
    result = await gateway.get_hotels_by_ids(ids)
    assert [h["hotel_id"] for h in result] == ids
@pytest.mark.asyncio
async def test_get_hotels_by_ids_empty_returns_empty(gateway):
    assert await gateway.get_hotels_by_ids([]) == []
    assert await gateway.get_hotels_by_ids(None) == []
@pytest.mark.asyncio
async def test_suggest_destinations_returns_list(gateway):
    result = await gateway.suggest_destinations({})
    assert isinstance(result, list)
    assert len(result) == 2
@pytest.mark.asyncio
async def test_find_transport_returns_list(gateway):
    result = await gateway.find_transport({})
    assert isinstance(result, list)
    assert len(result) == 2
@pytest.mark.asyncio
async def test_find_transfers_empty_when_no_source(gateway):
    """ТЗ п.4: пустой результат, если источника нет."""
    assert await gateway.find_transfers({"from_city": "Москва"}) == []
@pytest.mark.asyncio
async def test_get_climate_returns_none_when_no_source(gateway):
    assert await gateway.get_climate("dest_t_001", 11) is None
@pytest.mark.asyncio
async def test_get_climate_invalid_month_returns_none(gateway):
    assert await gateway.get_climate("dest_t_001", 0) is None
    assert await gateway.get_climate("dest_t_001", 13) is None
    assert await gateway.get_climate("", 11) is None
@pytest.mark.asyncio
async def test_retrieve_reviews_returns_empty_without_rag(gateway):
    """
    RAG-индекс не построен, embeddings нет —
    метод возвращает [] и НЕ падает (ТЗ п.2).
    """
    assert await gateway.retrieve_reviews("query", ["hotel_t_001"]) == []
@pytest.mark.asyncio
async def test_retrieve_reviews_empty_query_returns_empty(gateway):
    assert await gateway.retrieve_reviews("", ["hotel_t_001"]) == []
    assert await gateway.retrieve_reviews("   ", ["hotel_t_001"]) == []