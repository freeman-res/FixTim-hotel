from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field

class SourceType(str, Enum):
    DEMO = "demo"
    PUBLIC_API = "public_api"
    DERIVED = "derived"

class DataKind(str, Enum):
    HISTORICAL_OBSERVED = "historical_observed"
    CURRENT_SCHEDULE = "current_schedule"
    DERIVED = "derived"
    DEMO = "demo"

class Availability(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"

class PriceUnit(str, Enum):
    PER_TRIP = "per_trip"
    PER_PERSON = "per_person"

class TransportOption(BaseModel):
    """
    Единый формат для авиа / ЖД / автобусов (ТЗ №3, раздел 4).
    """
    transport_id: str
    mode: Literal["plane", "train", "bus"]

    # Идентификаторы (сохраняются без подмены)
    origin_airport_id: Optional[str] = Field(None, description="airports.ident")
    destination_airport_id: Optional[str] = None
    origin_icao: Optional[str] = None
    destination_icao: Optional[str] = None
    origin_iata: Optional[str] = None
    destination_iata: Optional[str] = None

    # География
    origin_city: Optional[str] = None
    destination_city: Optional[str] = None

    # Время / даты
    duration_minutes: Optional[int] = None

    # Достоверность (ТЗ №3, раздел 3 и 4)
    observed_flights: Optional[int] = None
    availability: Availability = Availability.UNKNOWN
    data_kind: DataKind
    source_type: SourceType
    source_name: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    last_observed_utc: Optional[datetime] = None
    is_demo: bool = False
    notes: Optional[str] = None