"""Проблема:
    flights_ru.csv — латиница ('Moscow', 'Kaliningrad'),
    cities.csv — кириллица ('Москва', 'Калининград').
    Без словаря find_transport(from_city='Москва') не находит рейсов.
Три источника алиасов
    1. KNOWN_ALIASES — ручной список топ-50 городов РФ.
    2. Транслит кириллицы (Калининград → kaliningrad).
    3. Координаты (municipality → ближайший город cities.csv в 100 км).
"""

from __future__ import annotations

import json
import logging
import math
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW     = PROJECT_ROOT / "data" / "raw"
DATA_NORM    = PROJECT_ROOT / "data" / "normalized"
DATA_NORM.mkdir(parents=True, exist_ok=True)

CITIES_CSV   = DATA_RAW / "transport_dataset_2026_plus_rossbus" / "cities.csv"
AIRPORTS_CSV = DATA_RAW / "airports.csv"
OUT_JSON     = DATA_NORM / "city_aliases.json"

RADIUS_KM_MATCH = 100.0
 
KNOWN_ALIASES: dict[str, str] = {
    "moscow": "Москва",
    "moskva": "Москва",
    "saint petersburg": "Санкт-Петербург",
    "st. petersburg": "Санкт-Петербург",
    "st petersburg": "Санкт-Петербург",
    "sankt-peterburg": "Санкт-Петербург",
    "petersburg": "Санкт-Петербург",
    "spb": "Санкт-Петербург",
    "novosibirsk": "Новосибирск",
    "yekaterinburg": "Екатеринбург",
    "ekaterinburg": "Екатеринбург",
    "kazan": "Казань",
    "nizhny novgorod": "Нижний Новгород",
    "chelyabinsk": "Челябинск",
    "omsk": "Омск",
    "samara": "Самара",
    "rostov-on-don": "Ростов-на-Дону",
    "rostov on don": "Ростов-на-Дону",
    "ufa": "Уфа",
    "krasnoyarsk": "Красноярск",
    "voronezh": "Воронеж",
    "perm": "Пермь",
    "volgograd": "Волгоград",
    "krasnodar": "Краснодар",
    "saratov": "Саратов",
    "tyumen": "Тюмень",
    "tolyatti": "Тольятти",
    "izhevsk": "Ижевск",
    "barnaul": "Барнаул",
    "ulyanovsk": "Ульяновск",
    "irkutsk": "Иркутск",
    "khabarovsk": "Хабаровск",
    "vladivostok": "Владивосток",
    "yaroslavl": "Ярославль",
    "makhachkala": "Махачкала",
    "tomsk": "Томск",
    "orenburg": "Оренбург",
    "kemerovo": "Кемерово",
    "novokuznetsk": "Новокузнецк",
    "ryazan": "Рязань",
    "astrakhan": "Астрахань",
    "penza": "Пенза",
    "lipetsk": "Липецк",
    "kirov": "Киров",
    "cheboksary": "Чебоксары",
    "tula": "Тула",
    "kaluga": "Калуга",
    "sochi": "Сочи",
    "kaliningrad": "Калининград",
    "murmansk": "Мурманск",
    "arkhangelsk": "Архангельск",
    "vologda": "Вологда",
    "pskov": "Псков",
    "veliky novgorod": "Великий Новгород",
    "smolensk": "Смоленск",
    "bryansk": "Брянск",
    "belgorod": "Белгород",
    "kursk": "Курск",
    "tambov": "Тамбов",
    "vladimir": "Владимир",
    "ivanovo": "Иваново",
    "kostroma": "Кострома",
    "tver": "Тверь",
    "cherepovets": "Череповец",
    "petrozavodsk": "Петрозаводск",
    "novorossiysk": "Новороссийск",
    "gelendzhik": "Геленджик",
    "anapa": "Анапа",
    "yalta": "Ялта",
    "sevastopol": "Севастополь",
    "simferopol": "Симферополь",
}


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_city_aliases")


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    a = (math.sin((rlat2 - rlat1) / 2) ** 2
         + math.cos(rlat1) * math.cos(rlat2) * math.sin((rlon2 - rlon1) / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def main() -> int:
    if not CITIES_CSV.exists():
        log.error("Нет %s", CITIES_CSV)
        return 2
    if not AIRPORTS_CSV.exists():
        log.error("Нет %s", AIRPORTS_CSV)
        return 2

    # --- 1. Города ---
    cities = pd.read_csv(CITIES_CSV, dtype=str)
    cities["latitude"]  = pd.to_numeric(cities["latitude"],  errors="coerce")
    cities["longitude"] = pd.to_numeric(cities["longitude"], errors="coerce")
    cities = cities.dropna(subset=["city", "latitude", "longitude"])
    log.info("cities.csv: %d городов", len(cities))

    # --- 2. Аэропорты, ТОЛЬКО Россия (иначе Moscow из США всё сломает) ---
    airports = pd.read_csv(AIRPORTS_CSV, dtype=str, low_memory=False)
    total_airports = len(airports)
    airports = airports[airports["iso_country"] == "RU"]
    log.info("airports.csv: %d → %d после фильтра iso_country='RU'",
             total_airports, len(airports))

    airports["latitude_deg"]  = pd.to_numeric(airports["latitude_deg"],  errors="coerce")
    airports["longitude_deg"] = pd.to_numeric(airports["longitude_deg"], errors="coerce")
    airports = airports.dropna(subset=["municipality", "latitude_deg", "longitude_deg"])
    airports = airports.drop_duplicates(subset=["municipality"])
    log.info("airports.csv: %d уникальных municipality РФ", len(airports))

    # --- Транслит ---
    cyr2lat = str.maketrans({
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    })

    def translit(s: str) -> str:
        return (s.lower().translate(cyr2lat)
                .replace(" ", "").replace("-", ""))

    cyr_by_translit: dict[str, str] = {}
    for _, row in cities.iterrows():
        cyr_by_translit.setdefault(translit(row["city"]), row["city"])

    city_coords = list(zip(cities["city"], cities["latitude"], cities["longitude"]))

    # --- 3. Сборка алиасов: хардкод — база, остальное — сверху ---
    aliases: dict[str, str] = dict(KNOWN_ALIASES)
    m_translit = 0
    m_coord = 0

    for _, ap in airports.iterrows():
        muni = str(ap["municipality"]).strip()
        if not muni or muni.lower() in aliases:
            continue
        muni_key = (muni.lower()
                    .replace(".", "").replace("-", "").replace(" ", ""))

        if muni_key in cyr_by_translit:
            aliases[muni.lower()] = cyr_by_translit[muni_key]
            m_translit += 1
            continue

        lat, lon = ap["latitude_deg"], ap["longitude_deg"]
        best, best_d = None, RADIUS_KM_MATCH
        for c_name, c_lat, c_lon in city_coords:
            d = haversine_km(lat, lon, c_lat, c_lon)
            if d < best_d:
                best_d, best = d, c_name
        if best:
            aliases[muni.lower()] = best
            m_coord += 1

    log.info("aliases: %d хардкод + %d транслит + %d координаты = %d",
             len(KNOWN_ALIASES), m_translit, m_coord, len(aliases))

    OUT_JSON.write_text(
        json.dumps(aliases, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    log.info("Записан %s", OUT_JSON.relative_to(PROJECT_ROOT))

    for sample in ("moscow", "saint petersburg", "kaliningrad",
                   "cherepovets", "sochi", "krasnodar", "kazan"):
        print(f"  {sample!r:20s} → {aliases.get(sample, '— MISS')!r}")
    return 0

sys.exit(main())