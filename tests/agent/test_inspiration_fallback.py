import asyncio

from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.agent.intent_router import IntentRouter
from backend.app.agent.schemas import TripPatch


class Catalog:
    async def suggest_destinations(self, filters):
        return [
            {"name": "Арзамас", "destination_id": "arz", "source": {"name": "catalog"}},
            {"name": "Сочи", "destination_id": "sochi", "source": {"name": "catalog"}},
            {"name": "Евпатория", "destination_id": "evp", "source": {"name": "catalog"}},
        ]


def test_sea_request_recovers_from_invalid_model_output():
    agent = AgentOrchestrator(Catalog())

    async def invalid_patch(*args):
        raise ValueError("invalid JSON")

    agent.parser.parse = invalid_patch
    response = asyncio.run(agent.handle_message(
        "s", "Хочу на море на 5 дней в ноябре, из Москвы, бюджет до 80 тысяч", {},
    ))
    assert response.status == "results"
    assert [item["name"] for item in response.destinations] == ["Сочи", "Евпатория"]
    assert response.updated_state["trip"]["origin_city"] == "Москва"
    assert response.updated_state["trip"]["max_total_budget"] == 80000


def test_sea_request_overrides_model_hotel_intent():
    assert IntentRouter.detect(
        "Хочу на море на 5 дней в ноябре", TripPatch(intent="hotel_search"),
        {"trip": {"origin_city": "Москва"}},
    ) == "inspiration"
