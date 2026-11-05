"""Выбор CatalogProvider по окружению (по умолчанию нормализованный JSON-каталог)."""
from __future__ import annotations
import os
from pathlib import Path
from .base import CatalogProvider
from .json import JsonProvider
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "catalog"
def get_provider(provider_name: str | None = None) -> CatalogProvider:
    name = (provider_name or os.getenv("CATALOG_PROVIDER") or "json").strip().lower()
    if name == "json":
        data_dir = Path(os.getenv("CATALOG_DATA_DIR", str(DEFAULT_DATA_DIR)))
        return JsonProvider(data_dir)



    raise ValueError(f"Неизвестный CATALOG_PROVIDER={name!r}. "
                     f"Доступно: 'json'.")
