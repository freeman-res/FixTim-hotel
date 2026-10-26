"""
Сборка документов и чанков из hotels.json.
ВАЖНО:
    У нас НЕТ настоящих отзывов 
    Единственный текст — hotel.search_text + name + type + city + address.
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
    s = re.sub(r"\s+", " ", str(s)).strip()
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
        parts = [p for p in (name, htype, city, address, search_text) if p]
        if not parts:
            continue
        full = " | ".join(parts)
        if len(full) < MIN_CHUNK_LEN:
            continue
        # Обогащаем source.type='derived' — раз текст собран из полей отеля,
        # он не является "review".
        src = dict(h.get("source") or {})
        src["type"] = "derived"
        src["origin_type"] = (h.get("source") or {}).get("type")

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