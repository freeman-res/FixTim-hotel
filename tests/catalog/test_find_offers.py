"""Правила фильтрации отелей (ТЗ№3 п.4).Главный инвариант: "неизвестно ≠ нет"."""
import pytest

@pytest.mark.asyncio
async def test_filter_by_city(gateway):
    result = await gateway.find_offers({"city": "Москва"})
    assert len(result) == 2
    assert all(h["location"]["city"] == "Москва" for h in result)


@pytest.mark.asyncio
async def test_city_normalization(gateway):
    result = await gateway.find_offers({"city": "москва"})
    assert len(result) == 2


@pytest.mark.asyncio
async def test_filter_by_stars_min_keeps_unknown(gateway):
    result = await gateway.find_offers({"stars_min": 3})
    ids = {h["hotel_id"] for h in result}
    assert "hotel_t_001" in ids
    assert "hotel_t_002" not in ids
    assert "hotel_t_003" in ids
@pytest.mark.asyncio
async def test_filter_by_price_max_keeps_unknown(gateway):
    result = await gateway.find_offers({"price_max": 5000})
    ids = {h["hotel_id"] for h in result}
    assert "hotel_t_001" not in ids
    assert "hotel_t_002" in ids
    assert "hotel_t_003" in ids
@pytest.mark.asyncio
async def test_filter_by_hotel_ids(gateway):
    result = await gateway.find_offers({"hotel_ids": ["hotel_t_002"]})
    assert len(result) == 1
    assert result[0]["hotel_id"] == "hotel_t_002"
@pytest.mark.asyncio
async def test_invalid_filters_return_empty(gateway):
    """Невалидные фильтры"""
    assert await gateway.find_offers({"hotel_ids": "not-a-list"}) == []
    assert await gateway.find_offers({"stars_min": "five"}) == []
@pytest.mark.asyncio
async def test_sort_puts_priced_hotels_first(gateway):
    """Сортировка в HotelsService.find_offers: сначала с ценой (по звёздам ↓),
    потом без цены. hotel_t_003 (price=None) должен быть последним."""
    result = await gateway.find_offers({})
    assert result[-1]["hotel_id"] == "hotel_t_003"