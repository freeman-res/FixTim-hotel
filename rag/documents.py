#Подготовка документов для RAG )
#chunk_text(text, size, overlap)  — разбить текст на фрагменты
#prepare_documents(reviews)       — превратить отзывы в чанки с метаданными
from typing import Any
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
def chunk_text(
    text: str,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,) -> list[str]:
    if not text or not text.strip():
        return []
    text = text.strip()
    # Короткий текст — один чанк
    if len(text) <= size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


def prepare_documents(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
   # Превращает список отзывов в список чанков с метаданными.
    documents = []
    for review in reviews:
        hotel_id = int(review["hotel_id"])
        source = review.get("source", "unknown")
        text = review.get("text", "")
        for i, chunk in enumerate(chunk_text(text)):
            documents.append({
                "id": f"{hotel_id}_{source}_{i}",
                "hotel_id": hotel_id,
                "source": source,
                "text": chunk,
            })
    return documents