
import pytest

@pytest.mark.asyncio
async def test_suggest_all_destinations(gateway):
    result = await gateway.suggest_destinations({})
    ids = {d["destination_id"] for d in result}
    assert ids == {"dest_t_001", "dest_t_002"}
@pytest.mark.asyncio
async def test_transport_available_from_origin(gateway):
    result = await gateway.suggest_destinations({"origin_city": "Москва"})
    by_id = {d["destination_id"]: d for d in result}

    kgd = by_id["dest_t_001"]
    assert kgd["transport_available"]["available"] is True
    assert "plane" in kgd["transport_available"]["types"]

    tula = by_id["dest_t_002"]
    assert tula["transport_available"]["available"] is True
    assert "bus" in tula["transport_available"]["types"]

@pytest.mark.asyncio
async def test_transport_available_no_route(gateway):
    """Origin без исходящих рейсов — available=False, types=[]."""
    result = await gateway.suggest_destinations({"origin_city": "Владивосток"})
    for d in result:
        assert d["transport_available"]["available"] is False
        assert d["transport_available"]["types"] == []

@pytest.mark.asyncio
async def test_climate_unknown_with_reason(gateway):
    """Климат: источника нет — status=unknown + reason (ТЗ п.4)."""
    result = await gateway.suggest_destinations({})
    for d in result:
        assert d["climate"]["status"] == "unknown"
        assert "not found" in d["climate"]["reason"]

@pytest.mark.asyncio
async def test_filter_by_region(gateway):
    result = await gateway.suggest_destinations({"region": "Тульская область"})
    assert len(result) == 1
    assert result[0]["name"] == "Тула"

@pytest.mark.asyncio
async def test_transport_min_price_aggregate(gateway):
    result = await gateway.suggest_destinations({"origin_city": "Москва"})
    by_id = {d["destination_id"]: d for d in result}
    assert by_id["dest_t_002"]["transport_available"]["min_transport_price_rub"] == 600
    assert by_id["dest_t_001"]["transport_available"]["min_transport_price_rub"] is None