"""Build a resumable SQLite file of hotel embeddings using the project's Embedder.

This SQLite output is a standalone artifact; the application's runtime Retriever
does not read it. To build the runtime FAISS/NumPy index, use
`python scripts/build_rag_index.py` with normalized `data/catalog/hotels.json`.

Run from the project root after starting local Ollama with bge-m3 installed:
    python -m backend.app.catalog.rag.vectorize_hotels
"""

from __future__ import annotations

import argparse
import array
import csv
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.catalog.rag.embeddings import Embedder


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CSV = ROOT / "datasets" / "hotels-russia-for-agent.csv"
DEFAULT_DB = ROOT / "artifacts" / "hotel_embeddings.sqlite3"


def build_text(row: dict[str, str]) -> str:
    """Create a compact factual description from fields present in the CSV."""
    parts: list[str] = []
    base = (row.get("city_agent_search_text") or "").strip()
    if base:
        parts.append(base)
    else:
        name = (row.get("name") or "").strip()
        kind = (row.get("type") or "").strip()
        city = (row.get("city_final") or row.get("city") or "").strip()
        if name:
            parts.append(f"Название: {name}")
        if kind:
            parts.append(f"Тип размещения: {kind}")
        if city:
            parts.append(f"Город: {city}")

    address = (row.get("address") or "").strip()
    if address:
        parts.append(f"Адрес: {address}")
    stars = (row.get("stars") or "").strip()
    if stars:
        parts.append(f"Категория: {stars} звезды")
    amenities = []
    for column, label in (("internet", "интернет"), ("parking", "парковка")):
        value = (row.get(column) or "").strip()
        if value:
            amenities.append(f"{label}: {value}")
    if amenities:
        parts.append("Удобства: " + "; ".join(amenities))
    text = ". ".join(parts).strip()
    if not text:
        raise ValueError(f"У отеля {row.get('hotel_key', '<без ключа>')} нет текста для эмбеддинга")
    return text


def init_db(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS hotel_embeddings (
            hotel_key TEXT PRIMARY KEY,
            osm_id TEXT,
            name TEXT NOT NULL,
            city TEXT,
            latitude REAL,
            longitude REAL,
            hotel_type TEXT,
            embedding_text TEXT NOT NULL,
            text_sha256 TEXT NOT NULL,
            model TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            vector_f32le BLOB NOT NULL,
            embedded_at TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS vectorization_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    connection.commit()


def metadata(connection: sqlite3.Connection, key: str, value: Any) -> None:
    connection.execute(
        "INSERT INTO vectorization_metadata(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, json.dumps(value, ensure_ascii=False)),
    )


def float32_le(values: list[float]) -> bytes:
    packed = array.array("f", values)
    if sys.byteorder != "little":
        packed.byteswap()
    return packed.tobytes()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--model", default="bge-m3")
    parser.add_argument("--host", default=None, help="Ollama URL; defaults to OLLAMA_URL or localhost")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum rows, useful for a small initial run")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size должен быть больше нуля")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit должен быть больше нуля")
    csv_path = args.csv.resolve()
    db_path = args.db.resolve()
    if not csv_path.is_file():
        raise SystemExit(f"CSV не найден: {csv_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    csv_hash = hashlib.sha256()
    with csv_path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            csv_hash.update(block)

    connection = sqlite3.connect(db_path)
    try:
        init_db(connection)
        metadata(connection, "source_csv", str(csv_path))
        metadata(connection, "source_sha256", csv_hash.hexdigest())
        metadata(connection, "model", args.model)
        metadata(connection, "vector_format", "little-endian float32")
        metadata(connection, "started_or_resumed_at", datetime.now(timezone.utc).isoformat())
        connection.commit()

        embedder = Embedder(model_name=args.model, host=args.host, batch_size=args.batch_size)
        pending: list[tuple[dict[str, str], str, str]] = []
        scanned = 0
        saved_now = 0

        def flush() -> None:
            nonlocal saved_now
            if not pending:
                return
            texts = [item[1] for item in pending]
            vectors = embedder.encode(texts)
            now = datetime.now(timezone.utc).isoformat()
            for (row, text, text_hash), vector in zip(pending, vectors, strict=True):
                lat = (row.get("latitude") or "").strip()
                lon = (row.get("longitude") or "").strip()
                connection.execute(
                    """INSERT INTO hotel_embeddings (
                        hotel_key, osm_id, name, city, latitude, longitude, hotel_type,
                        embedding_text, text_sha256, model, dimension, vector_f32le, embedded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(hotel_key) DO UPDATE SET
                        osm_id=excluded.osm_id, name=excluded.name, city=excluded.city,
                        latitude=excluded.latitude, longitude=excluded.longitude,
                        hotel_type=excluded.hotel_type, embedding_text=excluded.embedding_text,
                        text_sha256=excluded.text_sha256, model=excluded.model,
                        dimension=excluded.dimension, vector_f32le=excluded.vector_f32le,
                        embedded_at=excluded.embedded_at""",
                    (
                        row["hotel_key"], row.get("osm_id"), row.get("name") or "",
                        row.get("city_final") or row.get("city") or "",
                        float(lat) if lat else None, float(lon) if lon else None,
                        row.get("type"), text, text_hash, args.model, len(vector),
                        float32_le(vector), now,
                    ),
                )
            connection.commit()
            saved_now += len(pending)
            pending.clear()
            count = connection.execute("SELECT COUNT(*) FROM hotel_embeddings").fetchone()[0]
            if embedder.dim is not None:
                metadata(connection, "embedding_dimension", embedder.dim)
            metadata(connection, "embedded_count", count)
            connection.commit()
            print(f"Готово: {count} записей в базе; новых в этом запуске: {saved_now}", flush=True)

        with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            required = {"hotel_key", "name"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise SystemExit(f"В CSV отсутствуют обязательные столбцы: {', '.join(sorted(missing))}")
            for row in reader:
                scanned += 1
                if args.limit is not None and scanned > args.limit:
                    break
                hotel_key = (row.get("hotel_key") or "").strip()
                if not hotel_key:
                    raise ValueError(f"Пустой hotel_key в строке CSV {scanned + 1}")
                text = build_text(row)
                text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                old = connection.execute(
                    "SELECT text_sha256, model FROM hotel_embeddings WHERE hotel_key = ?",
                    (hotel_key,),
                ).fetchone()
                if old == (text_hash, args.model):
                    continue
                pending.append((row, text, text_hash))
                if len(pending) >= args.batch_size:
                    flush()
            flush()

        metadata(connection, "completed_at", datetime.now(timezone.utc).isoformat())
        connection.commit()
        count = connection.execute("SELECT COUNT(*) FROM hotel_embeddings").fetchone()[0]
        print(f"Векторизация завершена. Всего в базе: {count}. Размерность: {embedder.dim or 'без новых запросов'}.")
        print(f"Файл: {db_path}")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
