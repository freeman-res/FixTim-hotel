#!/usr/bin/env python3
"""
Если embeddings.py не подключён — скрипт падает с явной ошибкой
(это офлайн-шаг, не runtime). Во время runtime retriever корректно
вернёт [] и структурированный поиск продолжит работать.
"""

import sys
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.catalog.rag.indexer import build_index
from backend.app.catalog.rag.provider import make_provider, UnavailableProvider

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_rag_index")


def main():
    project_root = Path(__file__).resolve().parent.parent
    data_dir = Path(os.getenv("CATALOG_DATA_DIR", str(project_root / "data" / "catalog")))
    hotels_path = data_dir / "hotels.json"
    index_dir = Path(os.getenv("CATALOG_RAG_INDEX_DIR", str(project_root / "data" / "vector_index")))

    provider = make_provider()
    if isinstance(provider, UnavailableProvider):
        log.error("BGE-M3 от №2 не подключён: %s", provider.reason)
        log.error("Положи embeddings_bge_m3.py рядом с embeddings.py "
                  "(см. контракт EmbeddingsProvider) и повтори запуск.")
        sys.exit(1)

    result = build_index(hotels_path, index_dir, embeddings=provider)
    log.info("Готово: %s", result)


main()
