"""Exercise the deployed site and real Ollama agent through HTTP."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def request(base: str, path: str, payload: dict | None = None, timeout: int = 120):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            return json.loads(body) if path == "/health" or path.startswith("/api/") else body.decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise AssertionError(f"HTTP {exc.code} {path}: {exc.read()[:400]!r}") from exc


def good_response(label: str, result: dict) -> None:
    print(label, f"status={result.get('status')} stage={result.get('stage')}",
          f"hotels={len(result.get('hotels') or [])}",
          f"transport={len(result.get('transport_options') or [])}")
    if result.get("status") in {"error", "no_results"}:
        raise AssertionError(f"{label}: {result.get('reply')}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:18080")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    try:
        assert "Островок" in request(base, "/"), "site home page missing"
        assert "postChat" in request(base, "/js/api.js"), "site JavaScript missing"
        health = request(base, "/api/v1/health")
        assert health.get("status") == "ok", f"health: {health}"
        assert request(base, "/health") == {"status": "ok"}
        print("PASS: site, JavaScript and API health")

        first = request(base, "/api/v1/chat", {
            "message": "Найди отели в Казани с 20 по 22 ноября 2026, 1 взрослый, вылет из Москвы"
        })
        good_response("Hotel search", first)
        hotels = first.get("hotels") or []
        assert hotels, "real Ollama request returned no hotel cards"
        session = first.get("session_id")
        assert session, "session ID missing"
        assert first.get("state", {}).get("trip", {}).get("check_in") == "2026-11-20", \
            "model did not retain requested check-in date"
        assert first.get("state", {}).get("trip", {}).get("check_out") == "2026-11-22", \
            "model did not retain requested check-out date"

        hotel = request(base, "/api/v1/chat", {
            "session_id": session, "message": "Выбираю этот отель",
            "action": "select_hotel", "target_id": hotels[0]["hotel_id"]
        })
        good_response("Hotel selection", hotel)
        assert hotel.get("state", {}).get("selected", {}).get("hotel_offer_id") == hotels[0]["hotel_id"]
        if hotels[0].get("total_price") is not None:
            assert hotel.get("hotels", [{}])[0].get("total_price") == hotels[0]["total_price"], \
                "hotel tariff changed during selection"

        flight = request(base, "/api/v1/chat", {
            "session_id": session, "message": "Найди перелёт Москва — Казань 20 ноября 2026"
        })
        good_response("Flight search", flight)
        options = flight.get("transport_options") or []
        assert options, "no live or estimated flight option returned"
        option = next((row for row in options if row.get("type") == "plane"), None)
        assert option, "no flight option among transport results"
        print("Flight kind", option.get("record_kind"), "source", (option.get("source") or {}).get("name"))

        route = request(base, "/api/v1/chat", {
            "session_id": session, "message": "Добавляю перелёт",
            "action": "select_transport", "target_id": option["transport_id"]
        })
        good_response("Route and cart", route)
        cart = route.get("cart") or {}
        assert len(cart.get("items") or []) >= 3, "cart should include outbound, hotel and return status"
        assert cart.get("total", 0) > 0 and cart.get("is_demo") is True
        assert cart.get("scope") == "outbound_transport_and_hotel_only"
        assert any(item.get("type") == "return_transport" for item in cart["items"])
        if any(item.get("estimated") for item in cart["items"]):
            assert cart.get("has_estimates") is True, "synthetic prices are not labeled"

        returning = request(base, "/api/v1/chat", {
            "session_id": session, "message": "Найди обратную дорогу на 22 ноября",
            "action": "search_return_transport", "target_id": "2026-11-22"
        })
        good_response("Return search", returning)
        return_options = returning.get("transport_options") or []
        assert return_options and all(row.get("trip_leg") == "return" for row in return_options)
        chosen_return = request(base, "/api/v1/chat", {
            "session_id": session, "message": "Добавляю обратную дорогу",
            "action": "select_return_transport", "target_id": return_options[0]["transport_id"]
        })
        good_response("Return selection", chosen_return)
        assert chosen_return.get("state", {}).get("selected", {}).get("return_transport_id")
        assert any(item.get("type") == "return_transport" and item.get("price") is not None
                   for item in (chosen_return.get("cart") or {}).get("items") or [])

        booked = request(base, "/api/v1/checkout/confirm", {"session_id": session})
        assert booked.get("status") == "ok" and booked.get("booking_id", "").startswith("DEMO-")
        print("PASS: hotel, outbound, return, route and demo checkout")
        return 0
    except (AssertionError, OSError, ValueError, KeyError) as exc:
        print("FAIL:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
