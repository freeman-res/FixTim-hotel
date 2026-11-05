from fastapi.testclient import TestClient

from backend.app.main import app


def test_site_and_api_are_served_from_same_origin():
    client = TestClient(app)
    page = client.get("/")
    assert page.status_code == 200
    assert "Островок" in page.text
    assert client.get("/js/main.js").status_code == 200
    assert client.get("/api/v1/health").status_code == 200


def test_checkout_needs_an_existing_cart(monkeypatch):
    from backend.app import checkout
    monkeypatch.setattr(checkout.session_service, "get_session",
                        lambda session_id: {"state": {"trip": {"city": "Казань"}}})
    response = TestClient(app).post("/api/v1/checkout/confirm", json={"session_id": "s1"})
    assert response.status_code == 409
