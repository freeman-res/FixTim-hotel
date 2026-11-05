from backend.app.agent.trip_assembly import assemble_trip


def test_trip_assembly_uses_only_selected_outbound_and_hotel_prices():
    state = {
        "trip": {"city": "Казань", "origin_city": "Москва", "check_in": "2026-11-20",
                 "check_out": "2026-11-22", "adults": 2},
        "selected_hotel": {"hotel_id": "h1", "name": "Отель Казань", "total_price": 18000,
                           "currency": "RUB", "record_kind": "live_offer"},
        "selected_transport": {"transport_id": "t1", "type": "plane", "record_kind": "live_offer",
            "from": {"city": "Москва"}, "to": {"city": "Казань"},
            "schedule_date": "2026-11-20", "departure_utc": "2026-11-20T08:00:00+00:00",
            "price": {"amount_min_rub": 5000, "currency": "RUB",
                      "unit": "per_party_one_way", "party_size": 2}},
    }
    result = assemble_trip(state)
    assert len(result["itinerary"]["legs"]) == 2
    assert result["cart"]["total"] == 23000
    assert result["cart"]["scope"] == "outbound_transport_and_hotel_only"
    assert result["cart"]["has_estimates"] is False
    assert any("обрат" in warning.casefold() for warning in result["warnings"])


def test_trip_assembly_marks_synthetic_totals_and_unconfirmed_schedule():
    state = {
        "trip": {"city": "Казань", "check_in": "2026-11-20",
                 "check_out": "2026-11-22", "adults": 2},
        "selected_hotel": {"hotel_id": "h1", "name": "Отель Казань",
                           "price_estimate": {"amount_rub": 4500, "unit": "per_night"}},
        "selected_transport": {"transport_id": "t1", "type": "plane",
            "record_kind": "route_price_estimate", "from": {"city": "Москва"},
            "to": {"city": "Казань"}, "schedule_date": "2026-11-20",
            "price_estimate": {"amount_rub": 6000, "unit": "per_person_one_way"}},
    }
    result = assemble_trip(state)
    assert result["cart"]["total"] == 21000
    assert result["cart"]["has_estimates"] is True
    assert all(item["estimated"] for item in result["cart"]["items"] if item["price"] is not None)
    assert result["cart"]["items"][-1]["price"] is None
    assert any("не подтвержд" in warning for warning in result["warnings"])


def test_trip_assembly_does_not_total_nightly_price_without_exact_dates():
    state = {
        "trip": {"city": "Казань"},
        "selected_hotel": {"hotel_id": "h1", "name": "Отель Казань",
                           "price_estimate": {"amount_rub": 4500, "unit": "per_night"}},
        "selected_transport": {"transport_id": "t1", "type": "plane",
                               "record_kind": "route_price_estimate",
                               "price_estimate": {"amount_rub": 6000}},
    }
    result = assemble_trip(state)
    assert result["itinerary"]["legs"]
    assert result["cart"] is None
    assert any("точн" in warning for warning in result["warnings"])
