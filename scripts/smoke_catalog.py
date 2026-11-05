#!/usr/bin/env python3
"""
scripts/smoke_catalog.py
========================
Ручная end-to-end проверка каталога на data/catalog/*.json.

Запуск:
    python scripts/smoke_catalog.py

Что проверяет:
    1. Все 8 методов CatalogGateway вызываются без исключений.
    2. find_offers на реальных 30k отелях находит что-то для «Москва».
    3. find_transport находит plane + bus, фильтрует по типу.
    4. suggest_destinations обогащает transport_available.
    5. get_data_status честно показывает missing-источники.
    6. Связка латиница↔кириллица: find_transport(from_city="Москва")
       находит рейсы (если city_aliases построены).
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.catalog.service import get_catalog_gateway


async def main() -> int:
    gw = get_catalog_gateway()

    print("=" * 68)
    print("SMOKE: CatalogGateway на нормализованных data/catalog/*.json")
    print("=" * 68)


    print("\n[1] Статус источников")
    status = await gw.get_data_status()
    for name, info in status.items():
        if name == "rag":
            mark = "OK" if info.get("available") else "OFF"
            print(f"    {name:<14} {mark:<4} {info.get('reason') or ''}")
        else:
            mark = "OK" if info.get("available") else "MISS"
            extra = info.get("reason", "") if not info.get("available") else ""
            print(f"    {name:<14} {mark:<4} {extra}")


    print("\n[2] find_offers(city='Москва', stars_min=4)")
    hotels = await gw.find_offers({"city": "Москва", "stars_min": 4})
    print(f"    найдено: {len(hotels)}")
    for h in hotels[:3]:
        loc = h.get("location") or {}
        print(f"    - {h['hotel_id']:<15} {h.get('name', '')[:40]:<40} "
              f"city={loc.get('city')} stars={h.get('stars')}")


    print("\n[3] find_offers(price_max=5000) - price=None не должен отсечь")
    cheap = await gw.find_offers({"price_max": 5000})
    print(f"    найдено: {len(cheap)}")


    print("\n[4] find_transport(plane, Москва -> Калининград)")
    flights = await gw.find_transport({
        "type": "plane", "from_city": "Москва", "to_city": "Калининград",
    })
    print(f"    найдено: {len(flights)}")
    for f in flights[:2]:
        print(f"    - {f.get('callsign')} dep={f.get('departure_utc')} "
              f"dur={f.get('duration_minutes')}min price={f.get('price')}")


    print("\n[5] find_transport(bus) - первые 3 УНИКАЛЬНЫХ по trip_id")
    buses = await gw.find_transport({"type": "bus"})
    print(f"    найдено: {len(buses)}")
    seen_trips = set()
    for b in buses:
        tid = b.get("original_trip_id") or b["transport_id"]
        if tid in seen_trips:
            continue
        seen_trips.add(tid)
        p = b.get("price") or {}
        print(f"    - trip={tid:<18} "
              f"{b['from'].get('city')} -> {b['to'].get('city')} "
              f"от {p.get('amount_min_rub')} RUB")
        if len(seen_trips) >= 3:
            break


    print("\n[6] find_transport(train) without route - expected empty without network")
    trains = await gw.find_transport({"type": "train"})
    print(f"    найдено: {len(trains)} (ожидаем 0 без направления и даты)")


    print("\n[7] suggest_destinations(origin_city='Москва') - первые 3")
    dests = await gw.suggest_destinations({"origin_city": "Москва"})
    print(f"    найдено: {len(dests)}")
    for d in dests[:3]:
        ta = d.get("transport_available") or {}
        types = ",".join(ta.get("types") or []) or "-"
        minp = ta.get("min_transport_price_rub")
        print(f"    - {d['name']:<20} transport=[{types}] min={minp} RUB")


    print("\n[7b] Проверка городов с авиасообщением")
    for target in ("Калининград", "Сочи", "Казань", "Краснодар"):
        d = next((x for x in dests if x["name"] == target), None)
        if d:
            ta = d.get("transport_available") or {}
            types = ",".join(ta.get("types") or []) or "-"
            print(f"    - {target:<14} transport=[{types}]")


    print("\n[8] Связка: find_transport(from_city='Moscow') - должно найти рейсы")
    moscow_lat = await gw.find_transport({"from_city": "Moscow"})
    print(f"    найдено рейсов с 'Moscow': {len(moscow_lat)} "
          f"(если 0 - нужен scripts/build_city_aliases.py)")


    print("\n[9] RAG status")
    rag = await gw.rag_status()
    for k, v in rag.items():
        print(f"    {k}: {v}")

    print("\n" + "=" * 68)
    print("SMOKE DONE")
    print("=" * 68)
    return 0

sys.exit(asyncio.run(main()))
