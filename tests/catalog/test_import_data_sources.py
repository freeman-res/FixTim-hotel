import pytest

from scripts.import_data import validate_hotel_enrichment_sources


def test_optional_enrichment_directory_may_be_absent(tmp_path):
    assert validate_hotel_enrichment_sources(tmp_path / "not-created") is False


def test_enrichment_path_must_be_a_directory_if_it_exists(tmp_path):
    source_path = tmp_path / "hotel_enrichment"
    source_path.write_text("not a directory", encoding="utf-8")

    with pytest.raises(NotADirectoryError, match="hotel_enrichment"):
        validate_hotel_enrichment_sources(source_path)


def test_existing_enrichment_directory_requires_both_prepared_files(tmp_path):
    source_dir = tmp_path / "hotel_enrichment"
    source_dir.mkdir()
    (source_dir / "booking_hotels_ru.jsonl.gz").write_bytes(b"prepared")

    with pytest.raises(FileNotFoundError, match="hotel_price_references.jsonl.gz"):
        validate_hotel_enrichment_sources(source_dir)


def test_complete_enrichment_directory_is_accepted(tmp_path):
    source_dir = tmp_path / "hotel_enrichment"
    source_dir.mkdir()
    (source_dir / "booking_hotels_ru.jsonl.gz").write_bytes(b"metadata")
    (source_dir / "hotel_price_references.jsonl.gz").write_bytes(b"prices")

    assert validate_hotel_enrichment_sources(source_dir) is True
