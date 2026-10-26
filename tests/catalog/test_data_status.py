import pytest
@pytest.mark.asyncio
async def test_data_status_shows_available_sources(gateway):
    status = await gateway.get_data_status()
    assert status["hotels"]["available"] is True
    assert status["destinations"]["available"] is True
    assert status["transport"]["available"] is True
@pytest.mark.asyncio
async def test_data_status_shows_missing_sources_with_reason(gateway):
    status = await gateway.get_data_status()
    for missing in ("transfers", "climate", "reviews"):
        assert status[missing]["available"] is False
        assert "not found" in status[missing]["reason"]
@pytest.mark.asyncio
async def test_data_status_includes_rag(gateway):
    """RAG — не источник, но в диагностике должен быть со статусом."""
    status = await gateway.get_data_status()
    assert "rag" in status
    assert status["rag"]["available"] is False
    assert "build_rag_index" in status["rag"]["reason"]
@pytest.mark.asyncio
async def test_rag_status_endpoint(gateway):
    s = await gateway.rag_status()
    assert s["available"] is False
    assert s.get("chunks", 0) == 0