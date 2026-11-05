"""
Сборка документов и чанков из hotels.json.
ВАЖНО:
    У нас НЕТ настоящих отзывов 
    Текст составляется из описания, характеристик и поисковых полей отеля.
    Каждый чанк помечается:
        source.type = 'derived'
        note        = 'derived_from_hotel_metadata_and_search_text_not_user_review'
"""
from __future__ import annotations
import re
from dataclasses import asdict, dataclass
from typing import Iterable

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
MIN_CHUNK_LEN = 20

DERIVED_NOTE = "derived_from_hotel_metadata_and_search_text_not_user_review"
@dataclass
class RagChunk:
    chunk_id: str
    hotel_id: str
    text: str
    source: dict
    is_demo: bool
    note: str | None
def clean_text(s: str | None) -> str | None:
    """Trim + схлопывание пробелов. Пусто → None."""
    if not s:
        return None
    s = re.sub(r"\s+", " ", str(s).replace("\ufffd", " ")).strip()
    return s or None

def _split_text(text: str, size: int = CHUNK_SIZE,
                overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Нарезка с перекрытием — стандартный приём для RAG-чанков."""
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    step = size - overlap
    i = 0
    while i < len(text):
        chunks.append(text[i:i + size])
        i += step
    return chunks

def build_hotel_documents(hotels: Iterable[dict]) -> list[RagChunk]:
    """ Один отель → один или несколько чанков.
    В тексте — конкатенация всех доступных текстовых полей отеля.
    Ничего не выдумываем: если search_text пуст, но есть name и type —
    чанк всё равно полезен для поиска по типу/названию.
    """
    out: list[RagChunk] = []
    for h in hotels:
        name        = clean_text(h.get("name"))
        search_text = clean_text(h.get("search_text"))
        htype       = clean_text(h.get("type"))
        city        = clean_text((h.get("location") or {}).get("city"))
        address     = clean_text((h.get("location") or {}).get("address"))
        description = clean_text(h.get("description"))
        attractions = clean_text(h.get("attractions"))
        facilities = clean_text(h.get("facilities_text"))
        stars = clean_text(h.get("stars"))
        amenities = h.get("amenities") or {}
        verified_amenities = []
        if isinstance(amenities, dict):
            for key, value in amenities.items():
                if value is True or (isinstance(value, str) and value.strip().casefold() in {"yes", "true", "1", "да", "wlan", "wifi"}):
                    verified_amenities.append(str(key))
        parts = [p for p in (name, htype, city, address, description,
                             attractions, facilities, search_text) if p]
        if stars:
            parts.append(f"Категория: {stars} звезды")
        if verified_amenities:
            parts.append("Указанные в каталоге характеристики: " + ", ".join(verified_amenities))
        labels = h.get("amenity_labels") or []
        if isinstance(labels, (list, tuple)):
            labels = [clean_text(label) for label in labels]
            labels = [label for label in labels if label]
            if labels:
                parts.append("Удобства по данным источника: " + ", ".join(dict.fromkeys(labels)))
        if not parts:
            continue
        full = " | ".join(parts)
        has_searchable_anchor = bool(
            (name and len(name) >= 2)
            or any((city, address, description, attractions, facilities, search_text))
        )
        if len(full) < MIN_CHUNK_LEN and not has_searchable_anchor:
            continue


        src = dict(h.get("source") or {})
        src["type"] = "derived"
        src["origin_type"] = (h.get("source") or {}).get("type")
        source_details = h.get("source_details") or []
        if source_details:
            src["sources"] = [
                {
                    "source_record_id": item.get("source_record_id"),
                    "record_type": item.get("record_type"),
                    "match_status": item.get("match_status"),
                    "source": item.get("source") or {},
                }
                for item in source_details
            ]
        elif h.get("source"):
            src["sources"] = [{"source": h["source"]}]

        for i, chunk_text in enumerate(_split_text(full)):
            out.append(RagChunk(
                chunk_id=f"{h['hotel_id']}__chunk_{i}",
                hotel_id=h["hotel_id"],
                text=chunk_text,
                source=src,
                is_demo=bool(h.get("is_demo", True)),
                note=DERIVED_NOTE,
            ))
    return out
def chunks_to_dicts(chunks: list[RagChunk]) -> list[dict]:
    return [asdict(c) for c in chunks]
def dicts_to_chunks(items: Iterable[dict]) -> list[RagChunk]:
    return [RagChunk(**d) for d in items]
