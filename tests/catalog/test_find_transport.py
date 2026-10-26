import pytest
@pytest.mark.asyncio
async def test_find_transport_all_types(gateway):
    result = await gateway.find_transport({})
    types = {t["type"] for t in result}
    assert types == {"plane", "bus"}
@pytest.mark.asyncio
async def test_find_transport_by_type(gateway):
    planes = await gateway.find_transport({"type": "plane"})
    assert len(planes) == 1 and planes[0]["type"] == "plane"

    buses = await gateway.find_transport({"type": "bus"})
    assert len(buses) == 1 and buses[0]["type"] == "bus"
@pytest.mark.asyncio
async def test_find_transport_train_returns_empty(gateway):
    """ЖД-источника нет — честный [] (ТЗ п.4)."""
    assert await gateway.find_transport({"type": "train"}) == []
@pytest.mark.asyncio
async def test_find_transport_type_synonym(gateway):
    """'самолёт' → 'plane' через normalize_transport_type."""
    result = await gateway.find_transport({"type": "самолёт"})
    assert len(result) == 1
    assert result[0]["type"] == "plane"
@pytest.mark.asyncio
async def test_find_transport_by_city(gateway):
    assert len(await gateway.find_transport({"from_city": "Москва"})) == 2
    result = await gateway.find_transport({"to_city": "Калининград"})
    assert len(result) == 1 and result[0]["type"] == "plane"
@pytest.mark.asyncio
async def test_find_transport_by_max_price_keeps_unknown(gateway):
    """
    max_price=1000: bus (600) проходит, plane (None) НЕ отсекается.
    """
    result = await gateway.find_transport({"max_price": 1000})
    ids = {t["transport_id"] for t in result}
    assert "transport_bus_TEST2" in ids
    assert "transport_plane_TEST1" in ids
@pytest.mark.asyncio
async def test_find_transport_by_date_range(gateway):
    """Оба элемента фикстуры — на 2026-11-15."""
    within = await gateway.find_transport(
        {"date_from": "2026-11-15", "date_to": "2026-11-15"} )
    assert len(within) == 2
    later = await gateway.find_transport({"date_from": "2026-12-01"})
    assert later == []
@pytest.mark.asyncio
async def test_find_transport_invalid_type(gateway):
    """Невалидный type → [] (а не exception)."""
    assert await gateway.find_transport({"type": "spaceship"}) == []