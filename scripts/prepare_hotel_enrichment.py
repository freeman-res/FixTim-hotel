#!/usr/bin/env python3
"""Prepare the supplied hotel archives as compact, provenance-preserving JSONL."""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import logging
import re
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


log = logging.getLogger("prepare_hotel_enrichment")

_STAR_WORDS = {
    "onestar": 1,
    "twostar": 2,
    "threestar": 3,
    "fourstar": 4,
    "fivestar": 5,
}
_HOTEL_FIELDS = {
    "hotel name",
    "is top stays",
    "center distance",
    "metro distance",
    "price",
    "rating",
    "number of reviews",
    "description",
}
_CYRILLIC_TRANSLATION = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
})


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text or text.casefold() in {"nan", "none", "null", "n/a", "na", "-"}:
        return None
    return text


def _number(value: Any) -> float | None:
    text = _clean_text(value)
    if text is None:
        return None
    text = text.replace("\u00a0", "").replace(" ", "")
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        number = float(text)
    except (ValueError, OverflowError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _boolean(value: Any) -> bool | None:
    text = _clean_text(value)
    if text is None:
        return None
    if text.casefold() in {"true", "1", "yes", "y", "да"}:
        return True
    if text.casefold() in {"false", "0", "no", "n", "нет"}:
        return False
    return None


def _stars(value: Any) -> int | None:
    text = _clean_text(value)
    if text is None:
        return None
    compact = re.sub(r"[^a-z0-9]", "", text.casefold())
    if compact in _STAR_WORDS:
        return _STAR_WORDS[compact]
    match = re.search(r"\b([1-5])\s*(?:star|звезд)", text.casefold())
    return int(match.group(1)) if match else None


def _coordinates(value: Any) -> tuple[float | None, float | None]:
    text = _clean_text(value)
    if text is None:
        return None, None
    parts = re.split(r"[|,;]", text)
    if len(parts) != 2:
        return None, None
    latitude, longitude = _number(parts[0]), _number(parts[1])
    if latitude is None or longitude is None:
        return None, None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None, None
    return latitude, longitude


def _amenity_key(label: str) -> str:
    text = label.casefold()
    if "wi-fi" in text or "wi fi" in text or "wifi" in text or "интернет" in text:
        return "internet"
    if "парков" in text:
        return "parking"
    if "кондиционер" in text or "кондиционирован" in text:
        return "air_conditioning"
    if "завтрак" in text:
        return "breakfast"
    if "бассейн" in text:
        return "pool"
    if "животн" in text or "питомц" in text:
        return "pets_allowed"
    if "кухн" in text:
        return "kitchen"
    if "стиральн" in text or "прачечн" in text:
        return "laundry"
    if "лифт" in text:
        return "elevator"
    if "ресторан" in text:
        return "restaurant"
    translated = text.translate(_CYRILLIC_TRANSLATION)
    key = re.sub(r"[^a-z0-9]+", "_", translated).strip("_")
    return key or "amenity"


def _find_csv_member(archive: zipfile.ZipFile) -> zipfile.ZipInfo:
    members = [item for item in archive.infolist() if item.filename.casefold().endswith(".csv")]
    if not members:
        raise ValueError("ZIP archive has no CSV member")
    if len(members) > 1:
        members.sort(key=lambda item: item.filename.casefold())
        log.warning("ZIP contains multiple CSV files; using %s", members[0].filename)
    return members[0]


@contextmanager
def _csv_rows(source_zip: Path) -> Iterator[
    tuple[str, list[str], Iterator[dict[str, str | None]]]
]:
    """Open a ZIP CSV as a streaming DictReader, trimming whitespace from headers."""
    with zipfile.ZipFile(source_zip) as archive:
        member = _find_csv_member(archive)
        with archive.open(member) as probe:
            sample = probe.read(64 * 1024)
        try:
            sample.decode("utf-8-sig")
            encoding = "utf-8-sig"
        except UnicodeDecodeError:
            encoding = "cp1251"

        with archive.open(member) as raw:
            with io.TextIOWrapper(raw, encoding=encoding, errors="replace", newline="") as text:
                reader = csv.DictReader(text)
                reader.fieldnames = [
                    (field or "").strip().lstrip("\ufeff") for field in (reader.fieldnames or [])
                ]

                def rows() -> Iterator[dict[str, str | None]]:
                    for row in reader:
                        yield {
                            str(key).strip(): value
                            for key, value in row.items()
                            if key is not None
                        }

                yield member.filename.rsplit("/", 1)[-1], list(reader.fieldnames or []), rows()


def _write_jsonl_gz(path: Path, records: Iterator[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            for record in records:
                line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                compressed.write((line + "\n").encode("utf-8"))
                count += 1
    return count


def _booking_record(row: dict[str, str | None], source_file: str, row_number: int,
                    duplicate_code: bool) -> dict | None:
    name = _clean_text(row.get("HotelName"))
    code = _clean_text(row.get("HotelCode"))
    if name is None:
        return None
    source_record_id = f"booking_ru_{code}" if code else f"booking_ru_row_{row_number}"
    if duplicate_code:
        source_record_id = f"{source_record_id}__row_{row_number}"
    latitude, longitude = _coordinates(row.get("Map"))
    city = _clean_text(row.get("cityName"))
    facilities = _clean_text(row.get("HotelFacilities"))
    description = _clean_text(row.get("Description"))
    attractions = _clean_text(row.get("Attractions"))
    return {
        "source_record_id": source_record_id,
        "record_type": "booking_metadata",
        "name": name,
        "type": "hotel",
        "location": {
            "city": city,
            "city_source_raw": city,
            "address": _clean_text(row.get("Address")),
            "latitude": latitude,
            "longitude": longitude,
        },
        "stars": _stars(row.get("HotelRating")),
        "contacts": {
            "website": _clean_text(row.get("HotelWebsiteUrl")),
            "phone": _clean_text(row.get("PhoneNumber")),
            "fax": _clean_text(row.get("FaxNumber")),
        },
        "description": description,
        "attractions": attractions,
        "facilities_text": facilities,
        "amenities": {},
        "amenity_labels": [],
        "search_text": " | ".join(value for value in (description, facilities, attractions) if value) or None,
        "price": None,
        "price_references": [],
        "source": {
            "name": "Booking hotel metadata export",
            "type": "dataset",
            "format": "csv",
            "file": source_file,
            "row_number": row_number,
            "source_record_id": source_record_id,
            "url": _clean_text(row.get("HotelWebsiteUrl")),
            "retrieved_at": None,
            "data_as_of": None,
        },
        "is_demo": False,
    }


def prepare_booking_hotels(source_zip: Path, output_gz: Path) -> dict[str, int]:
    """Stream a mixed-country Booking hotel CSV and prepare only RU listings."""
    seen_codes: set[str] = set()
    rows_seen = rows_imported = rows_skipped_non_ru = rows_skipped_invalid = 0

    def records() -> Iterator[dict]:
        nonlocal rows_seen, rows_imported, rows_skipped_non_ru, rows_skipped_invalid
        with _csv_rows(Path(source_zip)) as (source_file, _fieldnames, rows):
            for row_number, row in enumerate(rows, start=2):
                rows_seen += 1
                if (_clean_text(row.get("countyCode")) or "").upper() != "RU":
                    rows_skipped_non_ru += 1
                    continue
                code = _clean_text(row.get("HotelCode"))
                duplicate_code = bool(code and code in seen_codes)
                if code:
                    seen_codes.add(code)
                record = _booking_record(row, source_file, row_number, duplicate_code)
                if record is None:
                    rows_skipped_invalid += 1
                    continue
                rows_imported += 1
                yield record

    _write_jsonl_gz(Path(output_gz), records())
    return {
        "rows_seen": rows_seen,
        "rows_imported": rows_imported,
        "rows_skipped_non_ru": rows_skipped_non_ru,
        "rows_skipped_invalid": rows_skipped_invalid,
    }


def _price_record(row: dict[str, str | None], source_file: str, row_number: int,
                  fieldnames: list[str]) -> dict | None:
    name = _clean_text(row.get("Hotel Name"))
    if name is None:
        return None
    source_record_id = f"hotel_data_row_{row_number}"
    description = _clean_text(row.get("Description"))
    city_text = (description or "").casefold().replace("ё", "е")
    city = "Санкт-Петербург" if "санкт-петербург" in city_text or "санкт петербург" in city_text else None

    source_amenities: dict[str, bool | None] = {}
    canonical_amenities: dict[str, bool | None] = {}
    for label in fieldnames:
        if label.casefold() in _HOTEL_FIELDS:
            continue
        value = _boolean(row.get(label))
        if value is None and _clean_text(row.get(label)) is None:
            continue
        source_amenities[label] = value
        key = _amenity_key(label)
        previous = canonical_amenities.get(key)
        if previous is None:
            canonical_amenities[key] = value
        elif value is True:
            canonical_amenities[key] = True

    true_labels = [label for label, value in source_amenities.items() if value is True]
    amount = _number(row.get("Price"))
    price_references = []
    if amount is not None and amount > 0:
        price_references.append({
            "amount": amount,
            "raw_value": _clean_text(row.get("Price")),
            "currency": None,
            "unit": None,
            "check_in": None,
            "check_out": None,
            "guest_count": None,
            "room_count": None,
            "observed_at": None,
            "status": "unverified_reference",
            "source_record_id": source_record_id,
            "source": {
                "name": "hotel_data.csv price dataset",
                "file": source_file,
                "row_number": row_number,
                "url": None,
                "retrieved_at": None,
                "data_as_of": None,
            },
            "context_note": (
                "В источнике не указаны валюта, дата проживания, число гостей/номеров "
                "или основа цены; это справочная сумма, не предложение для бронирования."
            ),
        })

    top_stays = _boolean(row.get("Is Top Stays"))
    rating = _number(row.get("Rating"))
    review_count = _number(row.get("Number of Reviews"))
    return {
        "source_record_id": source_record_id,
        "record_type": "hotel_price_reference",
        "name": name,
        "type": None,
        "location": {
            "city": city,
            "city_evidence": "explicit_description" if city else None,
            "address": None,
            "latitude": None,
            "longitude": None,
        },
        "stars": None,
        "description": description,
        "attractions": None,
        "facilities_text": None,
        "amenities": canonical_amenities,
        "amenities_source": source_amenities,
        "amenity_labels": true_labels,
        "guest_rating": {
            "score": rating,
            "scale": None,
            "review_count": int(review_count) if review_count is not None and review_count >= 0 else None,
            "source_label": "Rating",
        } if rating is not None or review_count is not None else None,
        "source_metrics": {
            "center_distance": _number(row.get("Center Distance")),
            "center_distance_unit": None,
            "metro_distance": _number(row.get("Metro Distance")),
            "metro_distance_unit": None,
        },
        "source_flags": {"top_stays": top_stays},
        "search_text": " | ".join(value for value in (description, " ".join(true_labels)) if value) or None,
        "price": None,
        "price_references": price_references,
        "source": {
            "name": "Hotel price and amenity dataset",
            "type": "dataset",
            "format": "csv",
            "file": source_file,
            "row_number": row_number,
            "source_record_id": source_record_id,
            "url": None,
            "retrieved_at": None,
            "data_as_of": None,
        },
        "is_demo": False,
    }


def prepare_price_references(source_zip: Path, output_gz: Path) -> dict[str, int]:
    """Prepare every hotel row while keeping its price and context separate."""
    rows_seen = rows_imported = rows_with_price_reference = rows_skipped_invalid = 0

    def records() -> Iterator[dict]:
        nonlocal rows_seen, rows_imported, rows_with_price_reference, rows_skipped_invalid
        with _csv_rows(Path(source_zip)) as (source_file, fieldnames, rows):
            for row_number, row in enumerate(rows, start=2):
                rows_seen += 1
                record = _price_record(row, source_file, row_number, fieldnames)
                if record is None:
                    rows_skipped_invalid += 1
                    continue
                rows_imported += 1
                rows_with_price_reference += bool(record["price_references"])
                yield record

    _write_jsonl_gz(Path(output_gz), records())
    return {
        "rows_seen": rows_seen,
        "rows_imported": rows_imported,
        "rows_with_price_reference": rows_with_price_reference,
        "rows_skipped_invalid": rows_skipped_invalid,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--booking-hotels-zip", required=True, type=Path)
    parser.add_argument("--price-dataset-zip", required=True, type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets" / "hotel_enrichment",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        "booking_hotels": prepare_booking_hotels(
            args.booking_hotels_zip, args.output_dir / "booking_hotels_ru.jsonl.gz"
        ),
        "price_references": prepare_price_references(
            args.price_dataset_zip, args.output_dir / "hotel_price_references.jsonl.gz"
        ),
    }
    print(json.dumps(stats, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
