"""Выбор провайдера по env CATALOG_PROVIDER.
Сейчас поддерживается только "json"
(import_data.py → data/demo/*.json → JsonProvider). Когда появятся csv/http/sql провайдеры — добавляются здесь одной строкой."""
from __future__ import annotations
import os
from pathlib import Path
from .base import CatalogProvider
from .json import JsonProvider
PROJECT_ROOT = Path(__file__).resolve().parents[4]  # backend/app/catalog/providers → корень
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "demo"
def get_provider(provider_name: str | None = None) -> CatalogProvider:
    name = (provider_name or os.getenv("CATALOG_PROVIDER") or "json").strip().lower()
    if name == "json":
        data_dir = Path(os.getenv("CATALOG_DATA_DIR", str(DEFAULT_DATA_DIR)))
        return JsonProvider(data_dir)
    # Будущие провайдеры добавляем здесь:
    # if name == "csv":  return CsvProvider(...)
    # if name == "http": return HttpProvider(...)
    raise ValueError(f"Неизвестный CATALOG_PROVIDER={name!r}. "
                     f"Доступно: 'json'.")