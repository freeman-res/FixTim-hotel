import gzip
import json
import zipfile

from scripts.prepare_hotel_enrichment import (
    prepare_booking_hotels,
    prepare_price_references,
)


def _make_zip(path, member_name, text):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member_name, text.encode("utf-8"))


def _read_jsonl_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def test_booking_preparation_filters_country_strips_headers_and_keeps_missing_coordinates(tmp_path):
    source = tmp_path / "hotels.zip"
    output = tmp_path / "hotels.jsonl.gz"
    _make_zip(
        source,
        "hotels.csv",
        "\ufeffcountyCode, countyName, HotelCode, HotelName, HotelRating, Address, Attractions, Description, HotelFacilities, Map, PhoneNumber, HotelWebsiteUrl\n"
        'RU,Russia,1001,Гранд Отель,FourStar,Невский 1,Эрмитаж 1 км,Тихие номера,WiFi parking,59.93|30.31,+7000,https://example.test/h/1001\n'
        'RU,Russia,1002,Без координат,Unrated,,,,,not-a-coordinate,,,\n'
        'US,United States,1003,Other Hotel,FiveStar,,,,,40.0|-70.0,,,\n',
    )

    stats = prepare_booking_hotels(source, output)
    records = _read_jsonl_gz(output)

    assert stats["rows_seen"] == 3
    assert stats["rows_imported"] == 2
    assert stats["rows_skipped_non_ru"] == 1
    assert records[0]["source_record_id"] == "booking_ru_1001"
    assert records[0]["name"] == "Гранд Отель"
    assert records[0]["stars"] == 4
    assert records[0]["location"]["latitude"] == 59.93
    assert records[0]["location"]["longitude"] == 30.31
    assert records[0]["description"] == "Тихие номера"
    assert records[0]["facilities_text"] == "WiFi parking"
    assert records[0]["source"]["url"] == "https://example.test/h/1001"
    assert records[0]["price"] is None
    assert records[1]["source_record_id"] == "booking_ru_1002"
    assert records[1]["location"]["latitude"] is None
    assert records[1]["location"]["longitude"] is None


def test_price_preparation_preserves_unverified_price_and_all_source_fields(tmp_path):
    source = tmp_path / "prices.zip"
    output = tmp_path / "prices.jsonl.gz"
    _make_zip(
        source,
        "hotel_data.csv",
        "Hotel Name,Is Top Stays,Center Distance,Metro Distance,Price,Rating,Number of Reviews,Description,Парковка,Бесплатный Wi-Fi\n"
        'Апартаменты Север,True,1.4,0.605,6800,9.9,12,"Расположены в Санкт-Петербурге",True,True\n'
        'Без цены,False,,,-,,0,,False,True\n',
    )

    stats = prepare_price_references(source, output)
    records = _read_jsonl_gz(output)

    assert stats["rows_seen"] == 2
    assert stats["rows_imported"] == 2
    assert stats["rows_with_price_reference"] == 1
    assert records[0]["source_record_id"] == "hotel_data_row_2"
    assert records[0]["location"]["city"] == "Санкт-Петербург"
    assert records[0]["price"] is None
    price_reference = records[0]["price_references"][0]
    assert price_reference["amount"] == 6800.0
    assert price_reference["raw_value"] == "6800"
    assert price_reference["currency"] is None
    assert price_reference["unit"] is None
    assert price_reference["check_in"] is None
    assert price_reference["check_out"] is None
    assert price_reference["guest_count"] is None
    assert price_reference["room_count"] is None
    assert price_reference["observed_at"] is None
    assert price_reference["status"] == "unverified_reference"
    assert price_reference["source_record_id"] == "hotel_data_row_2"
    assert price_reference["source"]["row_number"] == 2
    assert records[0]["guest_rating"]["score"] == 9.9
    assert records[0]["guest_rating"]["scale"] is None
    assert records[0]["guest_rating"]["review_count"] == 12
    assert records[0]["amenities"]["parking"] is True
    assert records[0]["amenities"]["internet"] is True
    assert records[0]["amenity_labels"] == ["Парковка", "Бесплатный Wi-Fi"]
    assert records[0]["source_metrics"]["center_distance"] == 1.4
    assert records[0]["source_metrics"]["center_distance_unit"] is None
    assert records[1]["price_references"] == []


def test_preparation_ids_and_output_are_stable(tmp_path):
    source = tmp_path / "prices.zip"
    first = tmp_path / "first.jsonl.gz"
    second = tmp_path / "second.jsonl.gz"
    _make_zip(source, "hotel_data.csv", "Hotel Name,Price\nHotel,1200\n")

    prepare_price_references(source, first)
    prepare_price_references(source, second)

    assert _read_jsonl_gz(first)[0]["source_record_id"] == "hotel_data_row_2"
    assert first.read_bytes() == second.read_bytes()
