from __future__ import annotations
import re
from datetime import date, datetime

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ALIASES_PATH = _PROJECT_ROOT / "data" / "normalized" / "city_aliases.json"
_alias_cache: dict[str, str] | None = None


def _load_aliases() -> dict[str, str]:
    global _alias_cache
    if _alias_cache is not None:
        return _alias_cache
    if _ALIASES_PATH.exists():
        try:
            _alias_cache = json.loads(_ALIASES_PATH.read_text(encoding="utf-8"))
            log.info("city_aliases: загружено %d алиасов", len(_alias_cache))
        except Exception as exc:
            log.warning("Не удалось загрузить %s: %s", _ALIASES_PATH, exc)
            _alias_cache = {}
    else:
        _alias_cache = {}
    return _alias_cache



def normalize_city(name: str | None) -> str | None:
    if not name:
        return None
    key = re.sub(r"\s+", " ", str(name).strip().lower())


    if key in CITY_ALIASES:
        return CITY_ALIASES[key]


    aliases = _load_aliases()
    if key in aliases:
        return aliases[key]


    return str(name).strip()




CITY_ALIASES: dict[str, str] = {

    "moscow": "Москва",
    "msk": "Москва",
    "saint petersburg": "Санкт-Петербург",
    "st. petersburg": "Санкт-Петербург",
    "st petersburg": "Санкт-Петербург",
    "spb": "Санкт-Петербург",
    "petersburg": "Санкт-Петербург",

    "москва": "Москва",
    "москвы": "Москва",
    "мск": "Москва",
    "санкт-петербург": "Санкт-Петербург",
    "спб": "Санкт-Петербург",
    "питер": "Санкт-Петербург",
    "питера": "Санкт-Петербург",
    "санкт-петербурга": "Санкт-Петербург",
}

CURRENCY_ALIASES: dict[str, str] = {
    "rub": "RUB", "rur": "RUB", "руб": "RUB", "₽": "RUB", "643": "RUB",
    "usd": "USD", "$": "USD", "840": "USD",
    "eur": "EUR", "€": "EUR", "978": "EUR",}

TRANSPORT_TYPE_ALIASES: dict[str, str] = {
    "plane": "plane", "air": "plane", "flight": "plane", "самолет": "plane",
    "самолёт": "plane", "авиа": "plane",
    "bus": "bus", "автобус": "bus",
    "train": "train", "rail": "train", "жд": "train", "поезд": "train",}

def normalize_currency(code: str | None, default: str = "RUB") -> str:
    """'руб'/'rur'/'643' -> 'RUB'. Пусто -> default (агент договорился RUB)."""
    if not code:
        return default
    return CURRENCY_ALIASES.get(str(code).strip().lower(), str(code).strip().upper())


def normalize_transport_type(t: str | None) -> str | None:
    """'самолёт' -> 'plane'. None остаётся None (значит 'любой тип')."""
    if not t:
        return None
    return TRANSPORT_TYPE_ALIASES.get(str(t).strip().lower(), str(t).strip().lower())


def normalize_date(value: str | date | None) -> str | None:
    """
    Приводит дату к ISO YYYY-MM-DD.
    Принимает '2026-11-15', '15.11.2026', '15/11/2026', date, datetime.
    Возвращает None, если формат не распознан (не бросаем исключение).
    """
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
def normalize_filters(filters: dict) -> dict:
    out = dict(filters)
    for key in ("city", "origin_city", "destination_city",
                "from_city", "to_city"):
        if key in out:
            out[key] = normalize_city(out[key])
    if "currency" in out:
        out["currency"] = normalize_currency(out["currency"])
    if "type" in out:
        out["type"] = normalize_transport_type(out["type"])
    for k in ("date_from", "date_to", "check_in", "check_out"):
        if k in out:
            out[k] = normalize_date(out[k])
    return out
