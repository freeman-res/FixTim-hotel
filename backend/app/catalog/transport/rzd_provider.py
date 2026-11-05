"""Bounded adapter from the unofficial RZD client to the transport catalog shape."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from rzd_api import Config, RzdClient

log = logging.getLogger(__name__)


class RzdPartialSearchError(RuntimeError):
    """A partial upstream response with no trains cannot prove no-results."""


class RzdTrainProvider:
    """Fetch direct trains; network and schema errors deliberately propagate."""

    def __init__(self, client=None):
        project_bundle = (Path(__file__).resolve().parents[4]
                          / "data" / "certs" / "rzd_ca_bundle.pem")
        ca_bundle = os.getenv("RZD_CA_BUNDLE") or (
            str(project_bundle) if project_bundle.is_file() else None
        )
        self.client = client or RzdClient(config=Config(
            connect_timeout=float(os.getenv("RZD_CONNECT_TIMEOUT", "3")),
            read_timeout=float(os.getenv("RZD_READ_TIMEOUT", "12")),
            retry_total=int(os.getenv("RZD_RETRY_TOTAL", "0")),
            retry_backoff=0,
            ca_bundle=ca_bundle,
        ))

    def search(self, from_city: str, to_city: str, departure_date: str) -> list[dict]:
        result = self.client.search_tickets_detailed(
            from_city, to_city, departure_date,
            only_with_seats=True,
            include_transfers=False,
        )
        trains = getattr(result, "trains", None)
        if not isinstance(trains, list):
            raise ValueError("RZD returned an invalid train list")
        partial = bool(getattr(result, "partial", False))
        if partial and not trains:
            raise RzdPartialSearchError("RZD returned an incomplete empty response")
        retrieved_at = datetime.now(timezone.utc).isoformat()
        options = []
        for train in trains:
            number = str(getattr(train, "display_number", None)
                         or getattr(train, "number", "")).strip()
            departure = getattr(train, "local_departure_time", None)
            arrival = getattr(train, "local_arrival_time", None)
            if not number or not departure:
                log.warning("Пропускаю неполную запись поезда без номера/отправления")
                continue
            departure = str(departure)
            arrival = str(arrival) if arrival else None
            duration_minutes = None
            if arrival:
                try:
                    start = datetime.fromisoformat(departure.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(arrival.replace("Z", "+00:00"))
                    duration_minutes = max(0, int((end - start).total_seconds() // 60))
                except (TypeError, ValueError):
                    log.warning("Не удалось вычислить длительность поезда %s", number)
            price = getattr(train, "min_price", None)
            options.append({
                "transport_id": f"rzd:{number}:{departure}",
                "type": "train",
                "from": {"city": from_city,
                         "station": getattr(train, "origin_name", None)},
                "to": {"city": to_city,
                       "station": getattr(train, "destination_name", None)},
                "departure_time_local": departure,
                "arrival_time_local": arrival,
                "schedule_date": departure[:10],
                "duration_minutes": duration_minutes,
                "train_number": number,
                "price": ({"amount_min_rub": float(price), "currency": "RUB",
                           "unit": "per_person", "scope": "per_person_minimum"}
                          if price is not None else None),
                "availability": {
                    "status": "unconfirmed",
                    "note": "Актуальное наличие и цена требуют проверки у РЖД.",
                },
                "source": {
                    "name": "РЖД",
                    "type": "public_api",
                    "format": "api",
                    "retrieved_at": retrieved_at,
                    "data_kind": "current_schedule",
                    "time_basis": "local_station_time",
                    "partial": partial,
                },
                "is_demo": False,
            })
        if trains and not options:
            raise ValueError("RZD returned train records without required route fields")
        return options
