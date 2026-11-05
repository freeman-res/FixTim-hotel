import asyncio
from datetime import date
from types import SimpleNamespace

from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.agent.schemas import TripPatch
from backend.app.agent.tools.weather import get_weather
from backend.app.agent.schemas import WeatherArgs


class WeatherCatalog:
    async def get_weather(self, city_or_id, target_date=None, month=None):
        if city_or_id != "Калининград":
            return None
        if month:
            return {"city": "Калининград", "weather": {"type": "climate_estimate",
                    "expected_temp_c": 4.2, "target_month": month,
                    "source": {"name": "Open-Meteo Historical Weather API"}}}
        return {"city": "Калининград", "weather": {"type": "exact_forecast",
                "target_date": target_date or date.today().isoformat(),
                "forecast": {"temp_min_c": 2, "temp_max_c": 7, "precipitation_mm": 1},
                "source": {"name": "Open-Meteo Forecast API"}}}


class PatchLLM:
    async def chat(self, messages, tools=None, response_format=None):
        return SimpleNamespace(message=SimpleNamespace(content=TripPatch(city="Калининград").model_dump_json()))


def test_weather_tool_uses_trip_city():
    result = asyncio.run(get_weather(WeatherArgs(), WeatherCatalog(),
                                     {"trip": {"city": "Калининград"}}))
    assert result["weather"]["type"] == "exact_forecast"


def test_weather_intent_returns_grounded_result_without_second_llm_call():
    agent = AgentOrchestrator(catalog=WeatherCatalog(), llm=PatchLLM())
    result = asyncio.run(agent.handle_message("s", "Какая погода в Калининграде?", {}))
    assert result.status == "results"
    assert result.weather["type"] == "exact_forecast"
    assert "прогноз" in result.reply.lower()


def test_weather_monthly_normal_is_labelled_as_average():
    agent = AgentOrchestrator(catalog=WeatherCatalog(), llm=PatchLLM())
    state = {"trip": {"city": "Калининград", "travel_month": 11}}
    result = asyncio.run(agent.handle_message("s", "Какая обычно погода в ноябре?", state))
    assert result.status == "results"
    assert result.weather["type"] == "climate_estimate"
    assert "средн" in result.reply.lower()
