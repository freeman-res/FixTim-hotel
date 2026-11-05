import gzip
import json

from backend.app.catalog.search.exact import filter_hotels
from backend.app.catalog.rag.documents import build_hotel_documents
from scripts.hotel_enrichment import load_prepared_hotel_sources


def _write_records(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def _base_hotel(hotel_id, name, city, latitude=None, longitude=None):
    return {
        "hotel_id": hotel_id,
        "name": name,
        "type": "hotel",
        "location": {
            "city": city,
            "address": None,
            "latitude": latitude,
            "longitude": longitude,
        },
        "stars": None,
        "amenities": {},
        "price": None,
        "source": {"name": "base catalog", "type": "dataset"},
    }


def _booking_record(source_id, name, city, latitude, longitude, description):
    return {
        "source_record_id": source_id,
        "record_type": "booking_metadata",
        "name": name,
        "type": "hotel",
        "location": {
            "city": city,
            "city_source_raw": city,
            "address": "Невский проспект, 1",
            "latitude": latitude,
            "longitude": longitude,
        },
        "stars": 4,
        "description": description,
        "attractions": "Эрмитаж",
        "facilities_text": "WiFi; парковка",
        "amenities": {"internet": True, "parking": True},
        "amenity_labels": ["WiFi", "парковка"],
        "price": None,
        "price_references": [],
        "source": {"name": "Booking metadata", "file": "hotels.csv", "row_number": 2},
        "is_demo": False,
    }


def _price_record(source_id, name, city, amount, description="Описание"):
    return {
        "source_record_id": source_id,
        "record_type": "hotel_price_reference",
        "name": name,
        "type": None,
        "location": {
            "city": city,
            "city_evidence": "explicit_description" if city == "Санкт-Петербург" else None,
            "latitude": None,
            "longitude": None,
            "address": None,
        },
        "stars": None,
        "description": description,
        "amenities": {"internet": True},
        "amenity_labels": ["WiFi"],
        "guest_rating": {"score": 9.1, "scale": None, "review_count": 12},
        "source_metrics": {"center_distance": 1.2, "center_distance_unit": None},
        "price": None,
        "price_references": [{
            "amount": amount,
            "currency": None,
            "unit": None,
            "check_in": None,
            "check_out": None,
            "guest_count": None,
            "room_count": None,
            "observed_at": None,
            "status": "unverified_reference",
            "source_record_id": source_id,
            "source": {"name": "price dataset", "row_number": 2},
        }],
        "source": {"name": "price dataset", "file": "hotel_data.csv", "row_number": 2},
        "is_demo": False,
    }


def test_metadata_merges_only_exact_name_and_close_coordinates_and_flags_candidate(tmp_path):
    source_dir = tmp_path / "prepared"
    _write_records(
        source_dir / "booking_hotels_ru.jsonl.gz",
        [
            _booking_record("booking_ru_1", "Гранд Отель", "Санкт-Петербург", 59.9301, 30.31, "Современные номера"),
            _booking_record("booking_ru_2", "Гранд Отель", "Санкт-Петербург", 59.9500, 30.33, "Другое здание"),
        ],
    )
    _write_records(source_dir / "hotel_price_references.jsonl.gz", [])
    base = [_base_hotel("hotel_1", "Гранд Отель", "Санкт-Петербург", 59.93, 30.31)]

    merged, stats = load_prepared_hotel_sources(base, source_dir)

    assert len(merged) == 2
    original = next(item for item in merged if item["hotel_id"] == "hotel_1")
    added = next(item for item in merged if item["hotel_id"] == "booking_ru_2")
    assert original["description"] == "Современные номера"
    assert original["stars"] == 4
    assert original["amenities"]["internet"] is True
    assert original["price"] is None
    assert original["source_details"][0]["source"]["name"] == "Booking metadata"
    assert added["data_quality"]["identity_status"] == "source_record_only"
    assert added["data_quality"]["possible_duplicate_candidate_ids"] == ["hotel_1"]
    assert stats["metadata_matched"] == 1
    assert stats["metadata_appended"] == 1


def test_unique_exact_city_match_attaches_reference_without_creating_bookable_price(tmp_path):
    source_dir = tmp_path / "prepared"
    _write_records(source_dir / "booking_hotels_ru.jsonl.gz", [])
    _write_records(
        source_dir / "hotel_price_references.jsonl.gz",
        [_price_record("hotel_data_row_2", "Отель Север", "Санкт-Петербург", 6800)],
    )
    base = [_base_hotel("hotel_1", "Отель Север", "Санкт-Петербург")]

    merged, stats = load_prepared_hotel_sources(base, source_dir)
    hotel = merged[0]

    assert len(merged) == 1
    assert hotel["price"] is None
    assert hotel.get("total_price") is None
    assert hotel["price_references"][0]["amount"] == 6800
    assert hotel["price_references"][0]["currency"] is None
    assert hotel["description"] == "Описание"
    assert hotel["guest_rating"]["score"] == 9.1
    assert stats["price_matched"] == 1
    assert filter_hotels(merged, {"price_max": 7000}) == merged
    assert filter_hotels(merged, {"require_price": True}) == []


def test_repeated_names_or_city_conflicts_are_not_merged(tmp_path):
    source_dir = tmp_path / "prepared"
    _write_records(source_dir / "booking_hotels_ru.jsonl.gz", [])
    _write_records(
        source_dir / "hotel_price_references.jsonl.gz",
        [
            _price_record("hotel_data_row_2", "Отель Север", "Санкт-Петербург", 6800),
            _price_record("hotel_data_row_3", "Отель Север", "Санкт-Петербург", 7200),
            _price_record("hotel_data_row_4", "Отель Север", "Москва", 6200),
        ],
    )
    base = [_base_hotel("hotel_1", "Отель Север", "Санкт-Петербург")]

    merged, stats = load_prepared_hotel_sources(base, source_dir)

    assert len(merged) == 4
    assert merged[0]["price_references"] == []
    assert all(h["price"] is None for h in merged)
    assert stats["price_matched"] == 0
    assert stats["price_appended"] == 3
    assert {h["hotel_id"] for h in merged[1:]} == {
        "hotel_data_row_2", "hotel_data_row_3", "hotel_data_row_4"
    }


def test_rag_indexes_source_descriptions_and_amenities_but_never_price(tmp_path):
    source_dir = tmp_path / "prepared"
    _write_records(source_dir / "booking_hotels_ru.jsonl.gz", [])
    _write_records(
        source_dir / "hotel_price_references.jsonl.gz",
        [_price_record("hotel_data_row_2", "Отель Север", "Санкт-Петербург", 6800,
                       description="Рядом с Невским проспектом")],
    )
    base = [_base_hotel("hotel_1", "Отель Север", "Санкт-Петербург")]
    merged, _ = load_prepared_hotel_sources(base, source_dir)

    chunks = build_hotel_documents(merged)
    chunk = next(item for item in chunks if item.hotel_id == "hotel_1")

    assert "Рядом с Невским проспектом" in chunk.text
    assert "WiFi" in chunk.text
    assert "6800" not in chunk.text
    assert chunk.source["sources"][0]["source_record_id"] == "hotel_data_row_2"
    assert chunk.note == "derived_from_hotel_metadata_and_search_text_not_user_review"


def test_rag_keeps_short_valid_hotel_names_and_skips_unreadable_name():
    chunks = build_hotel_documents([
        {"hotel_id": "short", "name": "Old Friends", "type": None,
         "location": {"city": None, "address": None}},
        {"hotel_id": "broken", "name": "\ufffd", "type": "hotel",
         "location": {"city": None, "address": None}},
    ])

    assert len(chunks) == 1
    assert chunks[0].hotel_id == "short"
    assert chunks[0].text == "Old Friends"
