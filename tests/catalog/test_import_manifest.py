from scripts.import_data import build_manifest


def test_manifest_uses_actual_hotel_and_transport_quality_counts():
    manifest = build_manifest({
        "hotels": {
            "rows_imported": 2,
            "quality": {
                "rows_missing_city": 1,
                "rows_missing_stars": 2,
                "rows_missing_price": 2,
            },
        },
        "transport_options": {
            "quality": {
                "plane_rows_missing_price": 1,
                "bus_rows_unconfirmed": 3,
                "bus_rows_dropped_missing_route_fields": 4,
                "bus_price_scope_counts": {
                    "route_level_range_NOT_per_departure": 2,
                    "modelled_price_estimate_not_live": 1,
                },
            },
        },
    })[0]

    limitations = "\n".join(manifest["known_limitations"])
    train_source = next(x for x in manifest["sources_missing"]
                        if x["expected_file"] == "train_options.json")

    assert "city missing 1/2 (50.0%)" in limitations
    assert "stars missing 2/2 (100.0%)" in limitations
    assert "price missing 2/2 (100.0%)" in limitations
    assert "flights: prices missing 1" in limitations
    assert "modelled_price_estimate_not_live=1" in limitations
    assert "4 source rows omitted" in limitations
    assert "RZD" in train_source["impact"]
