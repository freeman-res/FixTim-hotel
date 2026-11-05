from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.agent.schemas import TripPatch
from backend.app.agent.tools.catalog_adapter import AgentCatalogAdapter
from backend.app.main import app
from backend.app.sessions.models import Base


class LocalCatalog:
    async def suggest_destinations(self, filters):
        assert filters["origin_city"] == "Москва"
        return [{"destination_id": "dest_kazan", "name": "Казань",
                 "source": {"name": "local fixture"}, "is_demo": False}]

    async def get_destination(self, destination_id):
        return {"destination_id": "dest_kazan", "name": "Казань"} if destination_id == "dest_kazan" else None

    async def find_offers(self, filters):
        return [{"hotel_id": "h1", "name": "Отель Казань", "city": "Казань",
                 "location": {"city": "Казань"}, "stars": 4,
                 "price": None, "price_estimate": {"amount_rub": 4500, "unit": "per_night"},
                 "source": {"name": "local fixture"}}]

    async def get_hotel(self, hotel_id):
        if hotel_id != "h1":
            return None
        return {"hotel_id": "h1", "name": "Отель Казань", "city": "Казань",
                "location": {"city": "Казань"}, "stars": 4,
                "price": None, "price_estimate": {"amount_rub": 4500, "unit": "per_night"},
                "source": {"name": "local fixture"}}


class LocalLLM:
    async def chat(self, messages, tools=None, response_format=None):
        patch = TripPatch(origin_city="Москва", travel_month=11, intent="inspiration")
        return SimpleNamespace(message=SimpleNamespace(content=patch.model_dump_json()))


def test_chat_destination_hotel_and_session_persist_through_http(tmp_path, monkeypatch):
    from backend.app.api import chat as chat_api
    from backend.app.services import agent_service
    from backend.app.sessions import service as sessions_module

    engine = create_engine(f"sqlite:///{tmp_path / 'sessions.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(sessions_module, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(sessions_module, "create_tables", lambda: None)
    service = sessions_module.SessionService()
    monkeypatch.setattr(chat_api, "session_service", service)
    catalog = LocalCatalog()
    monkeypatch.setattr(agent_service, "get_catalog_gateway", lambda: catalog)
    monkeypatch.setattr(agent_service, "get_agent_orchestrator",
                        lambda: AgentOrchestrator(AgentCatalogAdapter(catalog), LocalLLM()))

    client = TestClient(app)
    first = client.post("/api/v1/chat", json={"message": "Куда поехать из Москвы в ноябре?"})
    assert first.status_code == 200
    first_data = first.json()
    assert first_data["stage"] == "destinations"
    assert first_data["destinations"][0]["destination_id"] == "dest_kazan"
    sid = first_data["session_id"]

    second = client.post("/api/v1/chat", json={"session_id": sid,
        "message": "Выбираю Казань", "action": "select_destination", "target_id": "dest_kazan"})
    assert second.status_code == 200
    second_data = second.json()
    assert second_data["stage"] == "hotels"
    assert second_data["hotels"][0]["price"] is None
    assert second_data["hotels"][0]["price_estimate"]["amount_rub"] == 4500

    third = client.post("/api/v1/chat", json={"session_id": sid,
        "message": "Выбираю отель", "action": "select_hotel", "target_id": "h1"})
    assert third.status_code == 200
    assert third.json()["state"]["selected"]["hotel_offer_id"] == "h1"
    assert "last_hotel_offers" not in third.json()["state"]
    assert "selected_hotel" not in third.json()["state"]
    assert "history" not in third.json()["state"]
    history = service.get_session(sid)
    assert history["state"]["selected"]["hotel_offer_id"] == "h1"
    assert len(history["messages"]) == 6

    ready_state = history["state"]
    ready_state["trip"].update({"check_in": "2026-11-20", "check_out": "2026-11-22", "adults": 1})
    ready_state["last_transport_options"] = [{
        "transport_id": "t1", "type": "plane", "record_kind": "route_price_estimate",
        "from": {"city": "Москва"}, "to": {"city": "Казань"},
        "schedule_date": "2026-11-20",
        "price_estimate": {"amount_rub": 6000, "unit": "per_person_one_way"},
    }]
    service.update_state(sid, ready_state)
    fourth = client.post("/api/v1/chat", json={"session_id": sid,
        "message": "Выбираю дорогу", "action": "select_transport", "target_id": "t1"})
    assert fourth.status_code == 200
    assert fourth.json()["stage"] == "checkout"
    assert fourth.json()["cart"]["total"] == 15000
    assert fourth.json()["cart"]["has_estimates"] is True
    assert fourth.json()["is_demo"] is True

    from backend.app import checkout
    monkeypatch.setattr(checkout, "session_service", service)
    booked = client.post("/api/v1/checkout/confirm", json={"session_id": sid})
    assert booked.status_code == 200
    assert booked.json()["booking_id"].startswith("DEMO-")
    assert service.get_session(sid)["state"]["demo_booked"] is True
